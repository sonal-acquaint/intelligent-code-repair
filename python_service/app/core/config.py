import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent

# Define the exact path to python_service/.env
ENV_FILE: Path = BASE_DIR / ".env"


# Load the .env file if it exists; also check current working directory as fallback
if ENV_FILE.exists():
    load_dotenv(ENV_FILE)
else:
    load_dotenv(Path.cwd() / ".env")



class Settings:
    """Application configuration settings loaded from environment variables or .env file.
    
    Each setting has a safe default value so the application can run even if 
    certain environment variables are missing.
    """

    host: str = os.getenv("HOST", "127.0.0.1")

    port: int = int(os.getenv("PORT", "8001"))

    ollama_base_url: str = os.getenv(
        "OLLAMA_BASE_URL",
        "http://127.0.0.1:11434",
    )

    ollama_model: str = os.getenv(
        "OLLAMA_MODEL",
        "qwen3:1.7b",
    )

    ollama_timeout: float = float(    
        os.getenv("OLLAMA_TIMEOUT", "120.0")
    )

    api_key: Optional[str] = os.getenv("AI_BUG_FIXER_API_KEY") or os.getenv("API_KEY")



@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached singleton instance of Settings.
    
    Using @lru_cache ensures we only create the Settings object once in memory
    instead of re-parsing environment variables on every HTTP request.
    """
    return Settings()


settings: Settings = get_settings()

