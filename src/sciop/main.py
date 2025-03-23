from typing import TYPE_CHECKING, Optional

import uvicorn

if TYPE_CHECKING:
    from sciop.config import Config


def main(config: Optional["Config"] = None) -> None:
    if config is None:
        from sciop.config import config
    uvicorn.run(
        "sciop.app:app",
        host=config.host,
        port=config.port,
        reload=config.reload,
        reload_includes=["*.py", "*.md", "*.yml"],
        lifespan="on",
        access_log=False,
    )
