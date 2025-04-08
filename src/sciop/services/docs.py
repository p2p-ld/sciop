from pathlib import Path
from time import time
from urllib.parse import urljoin

from mkdocs import config as mkdocs_config
from mkdocs.commands import build

from sciop.config import config
from sciop.logging import init_logger


def _find_mkdocs_config() -> Path:
    """Abstraction around path location in case we want to start packaging it"""
    return Path(__file__).parents[3].resolve() / "mkdocs.yml"


def build_docs() -> None:
    """
    Find and build documentation using mkdocs into `sciop/docs`.

    Mimicking the cli action:
    https://github.com/mkdocs/mkdocs/blob/7e4892ab2dd4a52efd95a9de407eee63310e0780/mkdocs/__main__.py#L280
    """
    logger = init_logger("services.docs")
    config_file = _find_mkdocs_config()
    if not config_file.exists():
        logger.warning("Docs could not be built, no mkdocs config was found at %s", config_file)
        return

    output_dir = Path(__file__).parents[1] / "docs"
    output_dir.mkdir(exist_ok=True)
    index = output_dir / "index.html"
    if index.exists() and (time() - index.stat().st_mtime) < 10:
        logger.debug("Not rebuilding docs, built less than 10 seconds ago")
        return

    cfg = mkdocs_config.load_config(config_file=str(config_file))
    cfg.plugins.on_startup(command="build", dirty=False)
    cfg.site_dir = output_dir
    cfg.site_url = urljoin(config.external_url, "/docs")
    build.build(cfg, dirty=False)
