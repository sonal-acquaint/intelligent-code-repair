from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class AnalyzePayload(BaseModel):
    """Payload representing an exception reported from the Laravel application."""

    id: Optional[str] = Field(default="test-probe", description="Unique identifier for the diagnostic request")
    timestamp: Optional[str] = Field(default=None, description="ISO timestamp of when the exception occurred")
    exception_class: Optional[str] = Field(default=None, description="Class name of the thrown exception")
    message: str = Field(..., description="Exception message")
    code: Any = Field(default=0, description="Exception code or status code")
    file: str = Field(..., description="File path where the exception originated")
    relative_file: Optional[str] = Field(default=None, description="Relative file path within Laravel app")
    line: Optional[int] = Field(default=None, description="Line number of the exception")
    code_snippet: Dict[str, str] = Field(default_factory=dict, description="Surrounding code lines with line numbers as keys")
    trace: Optional[List[Dict[str, Any]]] = Field(default=None, description="Parsed stack trace frames")
    environment: Optional[str] = Field(default="local", description="Laravel environment (local, production, etc.)")
    laravel_version: Optional[str] = Field(default=None, description="Version of the Laravel framework")
    php_version: Optional[str] = Field(default=None, description="PHP runtime version")
    context: Optional[Dict[str, Any]] = Field(default=None, description="HTTP request or CLI context metadata")
