from typing import List
from pydantic import BaseModel, Field


class FixItem(BaseModel):
    """Represents a suggested code repair patch for a file."""

    file: str = Field(..., description="Target file path to apply the fix to")
    diff: str = Field(..., description="Unified diff patch applying the fix")


class AnalyzeResponse(BaseModel):
    """Structured response returned to Laravel with diagnosis and patches."""

    status: str = Field(..., description="Analysis status: fix_available, connected, needs_more_context, or error")
    summary: str = Field(..., description="Root cause diagnosis and explanation of fix")
    fixes: List[FixItem] = Field(default_factory=list, description="List of proposed file diff patches")


class OllamaStatus(BaseModel):
    """Status details of Ollama local model service."""

    status: str = Field(..., description="Ollama connection state: connected, unavailable, or error")
    base_url: str = Field(..., description="Ollama server base URL")
    active_model: str = Field(..., description="Ollama model configured for analysis")
    available_models: List[str] = Field(default_factory=list, description="Models currently downloaded in Ollama")


class HealthResponse(BaseModel):
    """Health check response for the service."""

    status: str = Field(default="ok", description="Service status")
    service: str = Field(default="laravel-ai-bug-fixer", description="Service identifier")
    version: str = Field(default="1.0.0", description="Service version")
    ollama: OllamaStatus = Field(..., description="Ollama backend connection info")
