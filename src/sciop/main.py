from pathlib import Path
from typing import TYPE_CHECKING, Optional

import uvicorn

if TYPE_CHECKING:
    from sciop.config import Config


def main(config: Optional["Config"] = None) -> None:
    if config is None:
        from sciop.config import config
    in_pkg_docs = Path(__file__).parent / "docs"

    uvicorn.run(
        "sciop.app:app",
        host=config.host,
        port=config.port,
        reload=config.reload,
        reload_includes=["*.py", "*.md", "*.yml", "*.css"],
        reload_excludes=[str(in_pkg_docs.resolve())],
        lifespan="on",
        access_log=False,
    )
