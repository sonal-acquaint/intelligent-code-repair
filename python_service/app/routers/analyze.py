import logging
from fastapi import APIRouter, Depends, HTTPException
from app.schemas.error_report import AnalyzePayload
from app.schemas.fix_response import AnalyzeResponse
from app.services.ollama_service import OllamaService


router = APIRouter(tags=["Analysis"])

logger = logging.getLogger("ai_bug_fixer.ollama")

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
    try:
        logger.info("Received analyze request for exception: %s at %s:%s", payload.exception_class, payload.target_file, payload.line)
        result = await ollama_service.analyze_and_repair(payload)
        if result is None:
            logger.error("analyze_and_repair returned None for error %s", payload.id)
            raise HTTPException(
                status_code=500,
                detail="internalServerError",
            )
        return result
    except HTTPException:
        raise
    except Exception:
        logger.exception("Unexpected error in /analyze endpoint for error %s", payload.id)
        raise HTTPException(
            status_code=500,
            detail="internalServerError",
        )   
