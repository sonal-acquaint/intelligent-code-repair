from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, model_validator


class AnalyzePayload(BaseModel):
    """Payload representing an exception reported from Laravel."""

    id: Optional[str] = Field(default="test-probe")
    timestamp: Optional[str] = None
    exception_class: Optional[str] = None
    message: str = Field(...)
    code: Any = 0
    file: str = Field(...)
    relative_file: Optional[str] = None
    line: Optional[int] = None
    code_snippet: Dict[str, str] = Field(default_factory=dict)
    trace: Optional[List[Dict[str, Any]]] = None
    environment: Optional[str] = "local"
    laravel_version: Optional[str] = None
    php_version: Optional[str] = None
    context: Optional[Dict[str, Any]] = None

    @property
    def target_file(self) -> str:
        """Return the best available target file path."""
        return (self.relative_file or self.file).strip()

    @model_validator(mode="before")
    @classmethod
    def validate_payload(cls, values):
        if not isinstance(values, dict) or not values:
            raise ValueError(
                "Request body is empty. Please provide valid error details."
            )

        required_fields = ["message", "file"]

        for field in required_fields:
            value = values.get(field)

            if not isinstance(value, str) or not value.strip():
                raise ValueError(
                    f"'{field}' is required and cannot be empty."
                )

            if value.strip().lower() in {
                "string", "null", "none", "undefined"
            }:
                raise ValueError(
                    f"'{field}' contains an invalid placeholder value."
                )

        return values
