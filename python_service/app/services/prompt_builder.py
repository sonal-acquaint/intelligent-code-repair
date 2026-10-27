import json
import re

from app.schemas.error_report import AnalyzePayload


class PromptBuilder:
    """Build a structured Laravel error diagnosis prompt."""

    @staticmethod
    def build(payload: AnalyzePayload) -> str:
        raw_file = payload.relative_file or payload.file or "UnknownFile.php"
        file_path = raw_file.strip().replace("\\", "/").lstrip("/")

        match = re.search(
            r"(?:^|/)((?:app|src|routes|database|config|resources|bootstrap|public|tests)/.+)$",
            file_path,
        )
        target_file = match.group(1) if match else file_path
        target_line = payload.line or 1

        # Extract the exact crash line from snippet if available
        original_line = ""
        if payload.code_snippet:
            original_line = payload.code_snippet.get(str(target_line), "").rstrip("\r\n")

        snippet = "\n".join(
            f"{'->' if str(line) == str(target_line) else '  '} "
            f"{line}: {code}"
            for line, code in sorted(
                (payload.code_snippet or {}).items(),
                key=lambda item: int(item[0]) if item[0].isdigit() else 0,
            )
        ) or "Not available"

        trace = "\n".join(
            f"#{i} {frame.get('file', 'unknown')}:"
            f"{frame.get('line', '')} in "
            f"{frame.get('class', '')}{frame.get('type', '')}"
            f"{frame.get('function', 'unknown')}()"
            for i, frame in enumerate((payload.trace or [])[:8])
        ) or "No trace provided"

        context = json.dumps(payload.context, indent=2) if payload.context else "None"

        original_line_hint = (
            f"The exact original code line at line {target_line} to replace is:\n   {original_line}\n"
            if original_line
            else ""
        )

        return f"""
You are an expert Laravel debugging and code repair AI.

### ERROR
Class: {payload.exception_class}
Message: {payload.message}
File: {target_file}
Line: {target_line}
Environment: {payload.environment}
Laravel: {payload.laravel_version or 'N/A'}
PHP: {payload.php_version or 'N/A'}

### SOURCE CODE
```php
{snippet}
```

### STACK TRACE
{trace}

### CONTEXT
```json
{context}
```
### INSTRUCTIONS
1. Analyze the exception message, crash line ({target_line}), and source code of '{target_file}'.
2. Propose a minimal, precise code fix for '{target_file}' to resolve the bug safely.
{original_line_hint}
3. Replace the buggy code at line {target_line} with your corrected working code using a git unified diff patch:
   - Start with '--- a/{target_file}' and '+++ b/{target_file}'
   - Include hunk header '@@ -{target_line},1 +{target_line},N @@' (where N is the number of added replacement lines)
   - Prefix the exact original line from line {target_line} with '-'
   - Prefix each corrected replacement line with '+'
4. Set status to "fix_available" and explain the root cause and fix in "summary".

### REQUIRED JSON RESPONSE STRUCTURE:
{{
  "status": "fix_available",
  "summary": "Explain what caused the error and how the fix resolves it.",
  "fixes": [
    {{
      "file": "{target_file}",
      "diff": "--- a/{target_file}\\n+++ b/{target_file}\\n@@ -{target_line},1 +{target_line},1 @@\\n-{original_line or 'original_buggy_code'}\\n+fixed_code\\n"
    }}
  ]
}}
"""


 