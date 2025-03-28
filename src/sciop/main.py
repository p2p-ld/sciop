from pathlib import Path
from typing import TYPE_CHECKING, Optional

import uvicorn

if TYPE_CHECKING:
    from sciop.config import Config


def main(config: Optional["Config"] = None) -> None:
    if config is None:
        from sciop.config import config

    # add in-package docs to exclude list to avoid infinite reloads
    in_pkg_docs = Path(__file__).parent / "docs"
    # premake docs directory so it's correctly detected as directory in uvicorn watchdirs
    in_pkg_docs.mkdir(exist_ok=True)

    uvicorn.run(
        "sciop.app:app",
        host=config.host,
        port=config.port,
        reload=config.reload,
        reload_includes=["*.py", "*.md", "*.yml", "*.css"],
        reload_excludes=[str(in_pkg_docs)],
        lifespan="on",
        access_log=False,
    )
