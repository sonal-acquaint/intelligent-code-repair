"""
MCP Server for Laravel AI Bug Fixer
Allows AI assistants (Antigravity, Claude, Cursor) to diagnose and fix Laravel bugs using local Ollama.
"""
import sys
import logging
from pathlib import Path

# Ensure python_service root is in sys.path
sys.path.insert(0, str(Path(__file__).parent))

from mcp.server.fastmcp import FastMCP 
from app.schemas.error_report import AnalyzePayload
from app.services.ollama_service import OllamaService

# Initialize FastMCP server
mcp = FastMCP("Laravel AI Bug Fixer")
ollama_service = OllamaService()


logging.basicConfig(
    level=logging.INFO,
    stream=sys.stderr,  # <-- Prints to your terminal screen without corrupting stdout
    format="%(asctime)s [%(levelname)s] [MCP] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("mcp_server")


@mcp.tool()
async def check_ollama_health() -> str:
    """Check if the local Ollama LLM is reachable and list downloaded models."""
    status = await ollama_service.check_health()
    models = ", ".join(status.available_models) if status.available_models else "None"
    return f"Ollama Status: {status.status}\nAvailable Models: {models}"


@mcp.tool()
async def analyze_laravel_error(
    exception_class: str,
    message: str,
    file: str,
    line: int,
    code_snippet: dict[str, str],
    environment: str = "local",
    laravel_version: str = "11.0",
    php_version: str = "8.2",
) -> str:
    """Analyze a Laravel runtime exception using local Ollama and generate a git diff patch fix."""

    payload = AnalyzePayload(
        id="mcp-req",
        app_name="laravel-mcp-server",
        environment=environment,
        exception_class=exception_class,
        message=message,
        file=file,
        line=line,
        code_snippet=code_snippet,
        laravel_version=laravel_version,
        php_version=php_version,
    )

    result = await ollama_service.analyze_and_repair(payload)

    diff_output = ""
    for fix in result.fixes:
        diff_output += f"\nFile: {fix.file}\nDiff:\n{fix.diff}\n"

    return f"Status: {result.status}\nSummary: {result.summary}\n{diff_output}"


if __name__ == "__main__":
    mcp.run(transport="stdio")
