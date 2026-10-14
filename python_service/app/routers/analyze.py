from fastapi import APIRouter, Depends
from app.schemas.error_report import AnalyzePayload
from app.schemas.fix_response import AnalyzeResponse
from app.services.ollama_service import OllamaService


router = APIRouter(tags=["Analysis"])


# DEPENDENCY INJECTION PROVIDER
def get_ollama_service() -> OllamaService:
    return OllamaService()


@router.post(
    "/analyze",
    response_model=AnalyzeResponse,
    summary="Analyze and Fix Laravel Exception",
    description="Receives runtime exception context, queries Ollama, and generates a structured code fix with diff.",
)
async def analyze_exception(
    payload: AnalyzePayload,
    ollama_service: OllamaService = Depends(get_ollama_service),
) -> AnalyzeResponse:
    return await ollama_service.analyze_and_repair(payload)
