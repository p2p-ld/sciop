from functools import wraps
from logging import LogRecord, getLogger
from multiprocessing import Semaphore
from pathlib import Path
from threading import Thread
from time import time
from typing import Any
from urllib.parse import urljoin

from mkdocs import config as mkdocs_config
from mkdocs.commands import build

from sciop.config import get_config
from sciop.logging import init_logger

_DOCS_BUILDING = Semaphore(1)


# stop mkdocs from complaining about dirty builds
def _filter_dirty_build(record: LogRecord) -> bool:
    return "A 'dirty' build" not in record.msg


mkdocs_logger = getLogger("mkdocs.commands.build")
mkdocs_logger.addFilter(_filter_dirty_build)


def _find_mkdocs_config() -> Path:
    """Abstraction around path location in case we want to start packaging it"""
    return Path(__file__).parents[3].resolve() / "mkdocs.yml"


def build_docs(
    config_file: Path | None = None, output_dir: Path | None = None, dirty: bool = False
) -> Path | None:
    """
    Find and build documentation using mkdocs into `sciop/docs`.

    Mimicking the cli action:
    https://github.com/mkdocs/mkdocs/blob/7e4892ab2dd4a52efd95a9de407eee63310e0780/mkdocs/__main__.py#L280
    """
    logger = init_logger("services.docs")
    cfg = get_config()
    if config_file is None:
        config_file = _find_mkdocs_config()
    if not config_file.exists():
        logger.warning("Docs could not be built, no mkdocs config was found at %s", config_file)
        return

    if output_dir is None:
        output_dir = cfg.paths.docs
    output_dir.mkdir(exist_ok=True)
    index = output_dir / "index.html"

    # if testing or in prod, only build once per run
    timeout = 10 if cfg.env == "dev" else 1000

    if index.exists() and (time() - index.stat().st_mtime) < timeout:
        logger.debug("Not rebuilding docs, built less than %s seconds ago", timeout)
        return

    docs_cfg = mkdocs_config.load_config(config_file=str(config_file))
    # expose instance config to mkdocs
    docs_cfg.extra["instance_config"] = cfg.instance

    # if testing, don't bother with the git blame plugin, which is surprisingly expensive
    if cfg.env == "test":
        docs_cfg.plugins["git-authors"].config.enabled = False

    docs_cfg.plugins.on_startup(command="build", dirty=dirty)
    docs_cfg.site_dir = output_dir
    docs_cfg.site_url = urljoin(cfg.server.base_url, "/docs")

    logger.debug("Building docs...")
    try:
        build.build(docs_cfg, dirty=dirty)
    except Exception as e:
        logger.error(f"Failed to build docs: {e}")
    logger.debug("Completed building docs")
    return output_dir


@wraps(build_docs)
def build_docs_service(**kwargs: Any) -> None:
    """
    Build docs as a background thread, deduplicating across worker processes.

    Args:
        **kwargs: Forwarded to [build_docs][sciop.services.docs.build_docs]

    Returns:
        Path | None
    """
    should_build = _DOCS_BUILDING.acquire(False)
    if not should_build:
        return

    def _inner() -> None:
        try:
            build_docs(**kwargs)
        finally:
            _DOCS_BUILDING.release()

    thread = Thread(target=_inner)
    thread.start()
