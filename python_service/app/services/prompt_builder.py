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
            r"(?:^|/)((?:app|src|routes|database|config|resources)/.+)$",
            file_path,
        )
        target_file = match.group(1) if match else file_path
        target_line = payload.line or 1

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
3. Replace the buggy code line at line {target_line} with the corrected working code using a git unified diff patch:
   - Start with '--- a/{target_file}' and '+++ b/{target_file}'
   - Include hunk header '@@ -{target_line},1 +{target_line},1 @@'
   - Prefix the original buggy line from line {target_line} with '-'
   - Prefix the corrected replacement line with '+'
4. Set status to "fix_available" and explain the root cause and fix in "summary".

### REQUIRED JSON RESPONSE STRUCTURE:
{{
  "status": "fix_available",
  "summary": "Explain what caused the error and how the fix resolves it.",
  "fixes": [
    {{
      "file": "{target_file}",
      "diff": "--- a/{target_file}\\n+++ b/{target_file}\\n@@ -{target_line},1 +{target_line},1 @@\\n-buggy_code\\n+fixed_code\\n"
    }}
  ]
}}
"""


 