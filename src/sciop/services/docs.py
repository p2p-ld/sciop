from logging import LogRecord, getLogger
from pathlib import Path
from time import time
from urllib.parse import urljoin

from mkdocs import config as mkdocs_config
from mkdocs.commands import build

from sciop.config import config
from sciop.logging import init_logger


# stop mkdocs from complaining about dirty builds
def _filter_dirty_build(record: LogRecord) -> bool:
    return "A 'dirty' build" not in record.msg


mkdocs_logger = getLogger("mkdocs.commands.build")
mkdocs_logger.addFilter(_filter_dirty_build)


def _find_mkdocs_config() -> Path:
    """Abstraction around path location in case we want to start packaging it"""
    return Path(__file__).parents[3].resolve() / "mkdocs.yml"


def build_docs(
    config_file: Path | None = None, output_dir: Path | None = None, clean: bool = True
) -> Path | None:
    """
    Find and build documentation using mkdocs into `sciop/docs`.

    Mimicking the cli action:
    https://github.com/mkdocs/mkdocs/blob/7e4892ab2dd4a52efd95a9de407eee63310e0780/mkdocs/__main__.py#L280
    """
    logger = init_logger("services.docs")
    if config_file is None:
        config_file = _find_mkdocs_config()
    if not config_file.exists():
        logger.warning("Docs could not be built, no mkdocs config was found at %s", config_file)
        return

    if output_dir is None:
        output_dir = Path(__file__).parents[1] / "docs"
    output_dir.mkdir(exist_ok=True)
    index = output_dir / "index.html"

    # if testing or in prod, only build once per run
    timeout = 10 if config.env == "dev" else 1000

    if index.exists() and (time() - index.stat().st_mtime) < timeout:
        logger.debug("Not rebuilding docs, built less than %s seconds ago", timeout)
        return

    cfg = mkdocs_config.load_config(config_file=str(config_file))
    # expose instance config to mkdocs
    cfg.extra["instance_config"] = config.instance

    # if testing, don't bother with the git blame plugin, which is surprisingly expensive
    if config.env == "test":
        cfg.plugins["git-authors"].config.enabled = False

    cfg.plugins.on_startup(command="build", dirty=not clean)
    cfg.site_dir = output_dir
    cfg.site_url = urljoin(config.server.base_url, "/docs")

    logger.debug("Building docs...")
    try:
        build.build(cfg, dirty=not clean)
    except Exception as e:
        logger.error(f"Failed to build docs: {e}")
    logger.debug("Completed building docs")
    return output_dir
