import json
import logging
from pathlib import Path
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

        self.base_url: str = self.settings.ollama_base_url.rstrip("/")

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
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.base_url}/api/tags")
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
        target_file = payload.relative_file or payload.file or "UnknownFile.php"

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
                    f"{self.base_url}/api/generate", #ollama api call
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "stream": False,  # We want the complete response at once, not streaming chunks
                        "format": OLLAMA_JSON_SCHEMA,  # Enforce JSON output schema
                        "options": {
                            "temperature": 0.2,  # Low temperature makes output focused and deterministic
                        },
                    },
                )

            # Check if Ollama returned an HTTP error code (e.g. 404 model not found)
            if ollama_response.status_code != 200:
                error_summary = f"Ollama HTTP {ollama_response.status_code}: {ollama_response.text}"
                logger.error(error_summary)
                return AnalyzeResponse(
                    status="error",
                    summary=error_summary,
                    fixes=[],
                )

            ollama_data = ollama_response.json()
            raw_text = ollama_data.get("response", "")
            logger.info("Ollama response generated (%d characters). Parsing result...", len(raw_text))

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

        clean_text = raw_text.strip()
        target_file = payload.relative_file or payload.file

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
            fence_match = re.fullmatch(
                r"```(?:json)?\s*(.*?)\s*```",
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

        # 3. Handle structured JSON.
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

                # Require a recognizable unified diff.
                diff_lines = diff.splitlines()

                has_file_headers = (
                    len(diff_lines) >= 3
                    and diff_lines[0].startswith("--- ")
                    and diff_lines[1].startswith("+++ ")
                )
                has_hunk = any(
                    line.startswith("@@ ")
                    for line in diff_lines
                )

                if not has_file_headers or not has_hunk:
                    continue

                if not file_name:
                    continue

                fixes.append(
                    FixItem(
                        file=file_name,
                        diff=diff,
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

        # 4. Optional fallback: accept an explicit, recognizable diff block.
        diff_match = re.search(
            r"```(?:diff|patch)\s*\n(.*?)\n```",
            clean_text,
            re.DOTALL | re.IGNORECASE,
        )

        if diff_match and target_file:
            extracted_diff = diff_match.group(1).strip()
            diff_lines = extracted_diff.splitlines()

            has_file_headers = (
                len(diff_lines) >= 3
                and diff_lines[0].startswith("--- ")
                and diff_lines[1].startswith("+++ ")
            )
            has_hunk = any(
                line.startswith("@@ ")
                for line in diff_lines
            )

            if has_file_headers and has_hunk:
                return AnalyzeResponse(
                    status="fix_available",
                    summary=(
                        "Ollama returned a patch. Review it before applying."
                    ),
                    fixes=[
                        FixItem(
                            file=target_file,
                            diff=extracted_diff,
                        )
                    ],
                )

        # 5. No valid response: never create a fake patch.
        logger.warning(
            "Could not parse a valid Ollama response for error %s",
            payload.id,
        )

        return needs_context(
            "Ollama returned an unrecognized response. "
            "No patch was generated."
        )

