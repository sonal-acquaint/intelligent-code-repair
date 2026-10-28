import json
import logging
import re
from typing import Any, Dict, List, Optional

import httpx

from app.core.config import Settings, get_settings
from app.schemas.error_report import AnalyzePayload
from app.schemas.fix_response import (
    AnalyzeResponse,
    FixItem,
    OllamaStatus,
)
from app.services.prompt_builder import PromptBuilder

logger = logging.getLogger("ai_bug_fixer.ollama")


# This schema is passed directly to Ollama's `/api/generate` endpoint under the

OLLAMA_JSON_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "status": {
            "type": "string",
            "enum": [
                "fix_available",
                "needs_more_context",
                "no_fix_found",
                "error",
            ],
        },
        "summary": {
            "type": "string",
            "minLength": 1,
        },
        "fixes": {
            "type": "array",
            "maxItems": 1,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "file": {
                        "type": "string",
                        "minLength": 1,
                    },
                    "diff": {
                        "type": "string",
                        "minLength": 1,
                    },
                },
                "required": ["file", "diff"],
            },
        },
    },
    "required": ["status", "summary", "fixes"],
}



class OllamaService:
    """Service class responsible for communicating with the local Ollama LLM server.
    
    Responsibilities:
    1. Check connection health and query available local models via GET /api/tags.
    2. Send diagnostic prompts to Ollama's POST /api/generate endpoint.
    3. Parse, sanitize, and validate AI responses into structured AnalyzeResponse objects.
    """

    #Loads Ollama settings: URL, model name, and timeout.
    def __init__(self, settings: Optional[Settings] = None):
        self.settings: Settings = settings or get_settings()

        self.base_url: str = self.settings.ollama_base_url.rstrip("/") # read the ollama url 

        self.model: str = self.settings.ollama_model

        self.timeout: float = self.settings.ollama_timeout


    #Checks whether Ollama is running and lists installed models.
    async def check_health(self) -> OllamaStatus:
        """Inspect the connection to Ollama and retrieve installed models.
        
        Sends an asynchronous GET request to '{base_url}/api/tags'. If Ollama is running,
        it responds with HTTP 200 and a list of installed models.
        
        Returns:
            OllamaStatus: Connection status ('connected', 'unavailable', or 'error')
                          and list of downloaded models.
        """
        ollama_status = "unavailable"
        available_models: List[str] = []

        try: 
            async with httpx.AsyncClient(timeout=5.0) as client: # create asyncronous httpx client with timeout of 5.0 seconds
                resp = await client.get(f"{self.base_url}/api/tags") # send get request to ollama server to check connection
                if resp.status_code == 200:
                    ollama_status = "connected"
                    models_data = resp.json().get("models", [])
                    available_models = [m.get("name") for m in models_data if "name" in m]
        except Exception as exc:
            ollama_status = f"error: {str(exc)}"
            logger.warning("Failed to connect to Ollama server at %s: %s", self.base_url, exc)

        return OllamaStatus(
            status=ollama_status,
            base_url=self.base_url,
            active_model=self.model,
            available_models=available_models,
        )
        
    #Receives Laravel error details, builds a prompt, sends it to Ollama, and handles API errors.
    async def analyze_and_repair(self, payload: AnalyzePayload) -> AnalyzeResponse:
        """Send exception context to Ollama, parse diagnosis, and return code fix patches.
        
        Workflow:
        1. Handle connectivity probe check (artisan ai-bug-fixer:test).
        2. Build structured prompt with PromptBuilder.
        3. Dispatch HTTP POST to Ollama /api/generate with schema constraints.
        4. Pass the raw response to _parse_response() for multi-stage extraction.
        
        Args:
            payload (AnalyzePayload): Validated exception telemetry from Laravel.
            
        Returns:
            AnalyzeResponse: Root cause explanation, status, and unified diff patches.
        """
        # We reply immediately without invoking the heavy LLM.
        if payload.id == "test-connection-probe":
            logger.info("Responding to Laravel connectivity probe.")
            return AnalyzeResponse(
                status="connected",
                summary=f"Probe connection successful. Connected to Python service with Ollama ({self.model}).",
                fixes=[],
            )

        # --- Step 2: Build the AI Diagnostic Prompt ---
        prompt = PromptBuilder.build(payload)

        try:
            logger.info("Dispatching diagnostic prompt to Ollama model '%s'...", self.model)
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                ollama_response = await client.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "stream": False,
                        "format": OLLAMA_JSON_SCHEMA,
                        "keep_alive": "10m",
                        "think": False,
                        "options": {
                            "temperature": 0,
                            "num_predict": 180,
                            "num_ctx": 2048,
                        },
                    },
                )

            if ollama_response.status_code != 200:
                error_summary = (
                    f"Ollama HTTP {ollama_response.status_code}: "
                    f"{ollama_response.text}"
                )
                logger.error(error_summary)
                return AnalyzeResponse(
                    status="error",
                    summary="Ollama request failed. Check server logs.",
                    fixes=[],
                )

            ollama_data = ollama_response.json()

            logger.info(
                "Ollama timing | total=%.2fs | load=%.2fs | "
                "prompt=%.2fs | generation=%.2fs | tokens=%s",
                ollama_data.get("total_duration", 0) / 1e9,
                ollama_data.get("load_duration", 0) / 1e9,
                ollama_data.get("prompt_eval_duration", 0) / 1e9,
                ollama_data.get("eval_duration", 0) / 1e9,
                ollama_data.get("eval_count", 0),
            )

            raw_text = ollama_data.get("response", "")
            logger.info(
                "Ollama response generated (%d characters). Parsing result...",
                len(raw_text),
            )

            return self._parse_response(raw_text, payload)

        except httpx.ConnectError:
            msg = f"Cannot connect to Ollama at {self.base_url}. Ensure 'ollama serve' is running."
            logger.error(msg)
            return AnalyzeResponse(status="error", summary=msg, fixes=[])

        except httpx.TimeoutException:
            msg = f"Ollama request timed out after {self.timeout}s while analyzing {payload.exception_class}."
            logger.error(msg)
            return AnalyzeResponse(status="error", summary=msg, fixes=[])

        except Exception as exc:
            # Catch-all for unexpected runtime issues (e.g. network drops)
            msg = f"Unexpected error during AI diagnosis: {str(exc)}"
            logger.exception(msg)
            return AnalyzeResponse(status="error", summary=msg, fixes=[])

    
    def _parse_response(
        self,
        raw_text: str,
        payload: AnalyzePayload,
    ) -> AnalyzeResponse:
        """Parse Ollama output without inventing code patches."""

        # Strip any <think> reasoning tokens if present
        clean_text = re.sub(r"<think>.*?</think>", "", raw_text, flags=re.DOTALL).strip()
        target_file = payload.target_file

        def needs_context(summary: str) -> AnalyzeResponse:
            return AnalyzeResponse(
                status="needs_more_context",
                summary=summary,
                fixes=[],
            )

        if not clean_text:
            return needs_context(
                "Ollama returned an empty response. Please retry the analysis."
            )

        # 1. Parse the complete response as JSON.
        parsed_json = None

        try:
            candidate = json.loads(clean_text)
            if isinstance(candidate, dict):
                parsed_json = candidate
        except json.JSONDecodeError:
            pass

        # 2. If JSON is wrapped in a Markdown code fence, parse its contents.
        if parsed_json is None:
            fence_match = re.search(
                r"```(?:json)?\s*(\{.*?\})\s*```",
                clean_text,
                re.DOTALL | re.IGNORECASE,
            )
            if fence_match:
                try:
                    candidate = json.loads(fence_match.group(1))
                    if isinstance(candidate, dict):
                        parsed_json = candidate
                except json.JSONDecodeError:
                    pass

        # 3. Extract JSON object substring between outermost '{' and '}'
        if parsed_json is None:
            start = clean_text.find("{")
            end = clean_text.rfind("}")
            if start != -1 and end != -1 and end > start:
                try:
                    candidate = json.loads(clean_text[start : end + 1])
                    if isinstance(candidate, dict):
                        parsed_json = candidate
                except json.JSONDecodeError:
                    pass

        # 4. Handle structured JSON.
        if parsed_json is not None:
            raw_status = parsed_json.get("status")
            raw_summary = parsed_json.get("summary")
            raw_fixes = parsed_json.get("fixes")

            allowed_statuses = {
                "fix_available",
                "needs_more_context",
                "no_fix_found",
                "error",
            }

            if raw_status not in allowed_statuses:
                return needs_context(
                    "Ollama returned an invalid analysis status."
                )

            if not isinstance(raw_summary, str) or not raw_summary.strip():
                return needs_context(
                    "Ollama returned no valid diagnosis summary."
                )

            if not isinstance(raw_fixes, list):
                return needs_context(
                    "Ollama returned an invalid fixes list."
                )

            target_line = payload.line or 1
            original_line = (payload.code_snippet or {}).get(str(target_line), "").rstrip("\r\n")

            fixes: List[FixItem] = []

            for fix in raw_fixes:
                if not isinstance(fix, dict):
                    continue

                file_name = fix.get("file")
                diff = fix.get("diff")

                if not isinstance(file_name, str) or not file_name.strip():
                    file_name = target_file

                if not isinstance(diff, str) or not diff.strip():
                    continue

                normalized_diff = self._normalize_diff(
                    diff=diff,
                    target_file=file_name,
                    target_line=target_line,
                    original_line=original_line,
                )

                if not normalized_diff:
                    continue

                fixes.append(
                    FixItem(
                        file=file_name,
                        diff=normalized_diff,
                    )
                )

            # If valid diff patches were extracted, analysis outcome is fix_available
            if fixes:
                status = "fix_available"
            elif raw_status in ("needs_more_context", "no_fix_found"):
                status = raw_status
            else:
                status = "needs_more_context"
            return AnalyzeResponse(
                status=status,
                summary=raw_summary.strip(),
                fixes=fixes,
            )

        # 5. Optional fallback: accept an explicit unified diff block.
        diff_match = re.search(
            r"```(?:diff|patch)?\s*\n(--- a/.*?)\n```",
            clean_text,
            re.DOTALL | re.IGNORECASE,
        )
        if not diff_match:
            diff_match = re.search(
                r"(--- a/[^\n]+\n\+\+\+ b/[^\n]+\n@@[^\n]+@@[\s\S]+?)(?=\"\s*,|\"\s*\}|\n\n```|\Z)",
                clean_text,
            )

        if diff_match and target_file:
            extracted_diff = diff_match.group(1).strip()
            target_line = payload.line or 1
            original_line = (payload.code_snippet or {}).get(str(target_line), "").rstrip("\r\n")

            normalized_diff = self._normalize_diff(
                diff=extracted_diff,
                target_file=target_file,
                target_line=target_line,
                original_line=original_line,
            )

            if normalized_diff:
                return AnalyzeResponse(
                    status="fix_available",
                    summary=(
                        "Ollama returned a patch. Review it before applying."
                    ),
                    fixes=[
                        FixItem(
                            file=target_file,
                            diff=normalized_diff,
                        )
                    ],
                )

        # 6. Guaranteed fallback: safely return needs_more_context (NEVER return None!)
        logger.warning(
            "Could not parse a valid Ollama response for error %s",
            payload.id,
        )

        return needs_context(
            "Ollama response was incomplete or could not be parsed into a patch."
        )

    def _normalize_diff(
        self,
        diff: str,
        target_file: str,
        target_line: int,
        original_line: str = "",
    ) -> Optional[str]:
        """Normalize and validate a unified diff patch so git apply accepts it cleanly."""
        if not diff or not isinstance(diff, str):
            return None

        lines = [line.rstrip("\r") for line in diff.strip().splitlines()]
        if not lines:
            return None

        clean_file = target_file.strip().replace("\\", "/").lstrip("/")

        # Check if first lines have --- and +++ headers
        has_file_headers = (
            len(lines) >= 3
            and lines[0].startswith("--- ")
            and lines[1].startswith("+++ ")
        )
        if not has_file_headers:
            lines = [f"--- a/{clean_file}", f"+++ b/{clean_file}"] + [
                line for line in lines if not (line.startswith("---") or line.startswith("+++"))
            ]

        # Substitute placeholder -buggy_code with actual original code line if known
        if original_line:
            for i, line in enumerate(lines):
                if line.strip() in (
                    "-buggy_code",
                    "-original_buggy_code",
                    "-<buggy_code>",
                    "-...",
                    "-// buggy code",
                ):
                    lines[i] = f"-{original_line}"

        # Find hunk header and split content
        hunk_idx = -1
        for i, line in enumerate(lines):
            if line.startswith("@@ "):
                hunk_idx = i
                break

        content_lines = lines[hunk_idx + 1 :] if hunk_idx != -1 else lines[2:]
        clean_content = [
            l for l in content_lines
            if (l.startswith("-") or l.startswith("+") or l.startswith(" "))
            and not l.startswith("---")
            and not l.startswith("+++")
        ]

        removed_count = sum(1 for l in clean_content if l.startswith("-"))
        added_count = sum(1 for l in clean_content if l.startswith("+"))

        if removed_count == 0 and added_count == 0:
            return None

        # Reconstruct verified hunk header
        corrected_hunk = f"@@ -{target_line},{max(removed_count, 1)} +{target_line},{max(added_count, 1)} @@"
        result_lines = [f"--- a/{clean_file}", f"+++ b/{clean_file}", corrected_hunk] + clean_content

        return "\n".join(result_lines) + "\n"
