from fastapi import APIRouter, Depends
from app.schemas.fix_response import HealthResponse
from app.services.ollama_service import OllamaService

router = APIRouter(tags=["Health"])


def get_ollama_service() -> OllamaService:
    return OllamaService()


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health Check",
    description="Inspects service status and local Ollama model connection.",
)
@router.get(
    "/",
    response_model=HealthResponse,
    include_in_schema=False,
)
async def check_health(
    ollama_service: OllamaService = Depends(get_ollama_service),
) -> HealthResponse:
    ollama_status = await ollama_service.check_health()
    return HealthResponse(
        status="ok",
        service="laravel-ai-bug-fixer-python",
        version="1.0.0",
        ollama=ollama_status,
    )
