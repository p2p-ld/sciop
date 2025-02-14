"""
Jobs that might happen in the background, and otherwise encapsulate some
repeated operation not part of a route
"""

from pathlib import Path
from urllib.parse import urljoin

from mkdocs import config as mkdocs_config
from mkdocs.commands import build

from sciop.config import config


def _find_mkdocs_config() -> Path:
    """Abstraction around path location in case we want to start packaging it"""
    return Path(__file__).parents[2].resolve() / "mkdocs.yml"


def build_docs() -> None:
    """
    Find and build documentation using mkdocs into `sciop/docs`.

    Mimicking the cli action:
    https://github.com/mkdocs/mkdocs/blob/7e4892ab2dd4a52efd95a9de407eee63310e0780/mkdocs/__main__.py#L280
    """
    config_file = _find_mkdocs_config()
    cfg = mkdocs_config.load_config(config_file=str(config_file))

    dirty = False

    cfg.plugins.on_startup(command="build", dirty=dirty)

    output_dir = Path(__file__).parent / "docs"
    output_dir.mkdir(exist_ok=True)
    cfg.site_dir = output_dir
    cfg.site_url = urljoin(config.external_url, "/docs")

    build.build(cfg, dirty=dirty)
