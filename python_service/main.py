import logging
import uvicorn
from fastapi import FastAPI

from app.core.config import get_settings
from app.routers.analyze import router as analyze_router
from app.routers.health import router as health_router


# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("ai_bug_fixer")


def create_app() -> FastAPI:
    """Create and configure the FastAPI web application instance.
    
    Using the factory pattern allows:
    - Clean dependency management and configuration loading.
    - Easy creation of isolated app instances during automated testing.
    
    Returns:
        FastAPI: Fully configured ASGI application ready to handle requests.
    """
    settings = get_settings()

    application = FastAPI(
        title="Laravel AI Bug Fixer Service",
        description="Enterprise Python AI service diagnosing and repairing Laravel exceptions via local Ollama LLM.",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Register routers
    application.include_router(health_router)
    application.include_router(analyze_router)

    return application


app = create_app()


if __name__ == "__main__":
    settings = get_settings()
    logger.info("=" * 60)
    logger.info("AI Bug Fixer Python Service starting on http://%s:%d", settings.host, settings.port)
    logger.info("• Ollama Model : %s at %s", settings.ollama_model, settings.ollama_base_url)
    logger.info("• Health Check : http://%s:%d/health", settings.host, settings.port)
    logger.info("• Analyze API  : http://%s:%d/analyze", settings.host, settings.port)
    logger.info("• Swagger Docs : http://%s:%d/docs", settings.host, settings.port)
    logger.info("=" * 60)

    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
    )