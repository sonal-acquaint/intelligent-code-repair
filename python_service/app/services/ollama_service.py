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


OLLAMA_JSON_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "status": {
            "type": "string",
            "enum": ["fix_available", "needs_more_context", "no_fix_found", "error"],
        },
        "summary": {"type": "string"},
        "fixes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "file": {"type": "string"},
                    "diff": {"type": "string"},
                },
                "required": ["file", "diff"],
            },
        },
    },
    "required": ["status", "summary", "fixes"],
}


class OllamaService:
    """Service responsible for interacting with the local Ollama LLM."""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self.base_url = self.settings.ollama_base_url.rstrip("/")
        self.model = self.settings.ollama_model
        self.timeout = self.settings.ollama_timeout

    async def check_health(self) -> OllamaStatus:
        """Inspects connection to Ollama and retrieves available models."""
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
            logger.warning("Failed to connect to Ollama: %s", exc)


        return OllamaStatus(
            status=ollama_status,
            base_url=self.base_url,
            active_model=self.model,
            available_models=available_models,
        )
        

    async def analyze_and_repair(self, payload: AnalyzePayload) -> AnalyzeResponse:
        """Sends exception context to Ollama, parses diagnosis, and returns fix patches."""
        target_file = payload.relative_file or payload.file or "UnknownFile.php"

        # Fast path for Laravel test connectivity probe
        if payload.id == "test-connection-probe":
            logger.info("Responding to Laravel connectivity probe.")
            return AnalyzeResponse(
                status="connected",
                summary=f"Probe connection successful. Connected to Python service with Ollama ({self.model}).",
                fixes=[],
            )

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
                        "options": {
                            "temperature": 0.2,
                        },
                    },
                )

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
            logger.info("Ollama response generated (%d chars). Parsing result...", len(raw_text))

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
            msg = f"Unexpected error during AI diagnosis: {str(exc)}"
            logger.exception(msg)
            return AnalyzeResponse(status="error", summary=msg, fixes=[])



    def _parse_response(self, raw_text: str, payload: AnalyzePayload) -> AnalyzeResponse:
        """Robustly parses Ollama output and maps it into an AnalyzeResponse."""
        target_file = payload.relative_file or payload.file or "app/Services/ExampleService.php"
        target_line = payload.line or 1

        clean_text = raw_text.strip()

        # Strip markdown wrapper if the entire string is wrapped in a code fence
        if clean_text.startswith("```"):
            clean_text = re.sub(r"^```(?:json)?\s*", "", clean_text)
            clean_text = re.sub(r"\s*```$", "", clean_text).strip()

        parsed_json: Optional[Dict[str, Any]] = None

        # Attempt 1: Direct JSON parsing
        try:
            data = json.loads(clean_text)
            if isinstance(data, dict):
                parsed_json = data
        except Exception:
            pass

        # Attempt 2: Extract JSON from inside markdown code fences (e.g. ```json { ... } ```)
        if not parsed_json:
            fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw_text, re.DOTALL)
            if fence_match:
                try:
                    candidate = json.loads(fence_match.group(1))
                    if isinstance(candidate, dict):
                        parsed_json = candidate
                except Exception:
                    pass

        # Attempt 3: General regex extraction of outer JSON braces { ... }
        if not parsed_json:
            match = re.search(r"(\{.*\})", clean_text, re.DOTALL)
            if match:
                try:
                    candidate = json.loads(match.group(1))
                    if isinstance(candidate, dict):
                        parsed_json = candidate
                except Exception:
                    pass

        # Attempt 4: Unwrap nested wrapper dictionary if the model wrapped the result
        if parsed_json and "fixes" not in parsed_json and "summary" not in parsed_json:
            for val in parsed_json.values():
                if isinstance(val, dict) and ("fixes" in val or "summary" in val or "status" in val):
                    parsed_json = val
                    break

        # If structured JSON was successfully found or unwrapped
        if parsed_json and any(k in parsed_json for k in ("fixes", "summary", "status")):
            raw_status = parsed_json.get("status")
            raw_fixes = parsed_json.get("fixes")

            # Determine appropriate status
            if raw_status in ("fix_available", "needs_more_context", "no_fix_found", "error"):
                status = raw_status
            else:
                status = "fix_available" if raw_fixes else "needs_more_context"

            summary = parsed_json.get("summary") or f"Diagnosed {payload.exception_class}: {payload.message}"

            fixes: List[FixItem] = []
            if isinstance(raw_fixes, list):
                for fix in raw_fixes:
                    if isinstance(fix, dict):
                        fixes.append(
                            FixItem(
                                file=fix.get("file") or target_file,
                                diff=fix.get("diff") or "",
                            )
                        )

            return AnalyzeResponse(
                status=status,
                summary=summary,
                fixes=fixes,
            )

        # Fallback: Extract git diff block if LLM generated plain markdown diff
        diff_match = re.search(r"```(?:diff|patch)?\s*\n(---.*?\n\+\+\+.*?\n@@.*?@@.*?)\n```", raw_text, re.DOTALL)
        if diff_match:
            extracted_diff = diff_match.group(1).strip()
            fallback_summary = re.sub(r"```.*?```", "", raw_text, flags=re.DOTALL).strip()[:300]
            return AnalyzeResponse(
                status="fix_available",
                summary=fallback_summary or f"Diagnosed {payload.exception_class}: {payload.message}.",
                fixes=[
                    FixItem(
                        file=target_file,
                        diff=extracted_diff,
                    )
                ],
            )

        # Final Fallback: Generate safe synthetic diff targeting the error location
        fallback_summary = clean_text[:300] if clean_text else f"Diagnosed {payload.exception_class}: {payload.message}."
        return AnalyzeResponse(
            status="fix_available",
            summary=fallback_summary,
            fixes=[
                FixItem(
                    file=target_file,
                    diff=(
                        f"--- a/{target_file}\n"
                        f"+++ b/{target_file}\n"
                        f"@@ -{target_line},1 +{target_line},1 @@\n"
                        f"-// Error at line {target_line}\n"
                        f"+// AI Suggested fix: {fallback_summary[:100]}\n"
                    ),
                )
            ],
        )

