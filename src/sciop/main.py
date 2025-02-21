import uvicorn

from sciop.config import config


def main() -> None:
    uvicorn.run(
        "sciop.app:app",
        host=config.host,
        port=config.port,
        reload=config.reload,
        reload_includes=["*.py", "*.md", "*.yml"],
        lifespan="on",
        access_log=False,
    )
