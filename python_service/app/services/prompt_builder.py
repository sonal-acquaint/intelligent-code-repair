import json
from app.schemas.error_report import AnalyzePayload


class PromptBuilder:
    """Builds structured diagnosis prompts from Laravel exception payloads."""

    @staticmethod
    def build(payload: AnalyzePayload) -> str:
        target_file = payload.relative_file or payload.file or "UnknownFile.php"
        target_line = payload.line or 1

        # Format code snippet with line numbers and pointer to offending line
        snippet_text = "Not available"
        if payload.code_snippet:
            sorted_snippet = []
            for k, v in payload.code_snippet.items():
                try:
                    line_no = int(k)
                except ValueError:
                    line_no = 0
                sorted_snippet.append((line_no, k, v))
            sorted_snippet.sort(key=lambda item: item[0])
            snippet_text = "\n".join(
                f"{'-> ' if str(target_line) == str(k) else '   '}{k}: {v}"
                for _, k, v in sorted_snippet
            )

        # Format top stack trace frames
        trace_text = "No trace provided"
        if payload.trace:
            frames = []
            for i, frame in enumerate(payload.trace[:8]):
                f_file = frame.get("file", "unknown")
                f_line = frame.get("line", "")
                f_class = frame.get("class", "")
                f_type = frame.get("type", "")
                f_func = frame.get("function", "")
                caller = f"{f_class}{f_type}{f_func}()" if f_func else "unknown"
                frames.append(f"#{i} {f_file}:{f_line} in {caller}")
            trace_text = "\n".join(frames)

        # Request / context details
        context_str = json.dumps(payload.context, indent=2) if payload.context else "None"

        return f"""You are an expert Laravel developer and automated code repair AI.
A Laravel application encountered an exception at runtime.

### EXCEPTION DETAILS
- Class: {payload.exception_class}
- Message: {payload.message}
- File: {target_file}
- Line: {target_line}
- Environment: {payload.environment}
- Laravel: {payload.laravel_version or 'N/A'} | PHP: {payload.php_version or 'N/A'}

### SOURCE CODE SNIPPET (Target file around line {target_line}):
```php
{snippet_text}
```

### STACK TRACE:
{trace_text}

### REQUEST / EXECUTION CONTEXT:
```json
{context_str}
```

### INSTRUCTIONS:
1. Diagnose why this exception was thrown.
2. Propose a precise fix for '{target_file}' to resolve the bug safely.
3. Generate a git unified diff patch applying the change to '{target_file}'.

Respond ONLY with a valid JSON object strictly matching this schema:
{{
  "status": "fix_available",
  "summary": "Concise 1-3 sentence explanation of root cause and fix.",
  "fixes": [
    {{
      "file": "{target_file}",
      "diff": "--- a/{target_file}\\n+++ b/{target_file}\\n@@ ... @@\\n-old code\\n+new code\\n"
    }}
  ]
}}"""
