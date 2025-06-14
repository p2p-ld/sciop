from typing import TYPE_CHECKING, Optional

import uvicorn

if TYPE_CHECKING:
    from sciop.config.main import Config


def main(config: Optional["Config"] = None) -> None:
    if config is None:
        from sciop.config import get_config

        config = get_config()

    exclude = []

    include = ["*.py", "*.yml", "*.yaml"]
    if config.services.docs.enabled:
        # watch markdown files
        include.append("*.md")

        # Exclude built docs dir
        exclude.append(str(config.paths.docs))

    uvicorn.run(
        "sciop.app:app",
        host=config.server.host,
        port=config.server.port,
        reload=config.reload_uvicorn,
        reload_includes=include,
        reload_excludes=exclude,
        lifespan="on",
        access_log=False,
    )
