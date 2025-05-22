from pathlib import Path
from typing import TYPE_CHECKING, Optional

import click

from sciop.cli.common import config_option

if TYPE_CHECKING:
    pass


@click.command()
@config_option
@click.option("--port", required=False, type=int)
def start(port: Optional[int] = None, config: Optional[Path] = None) -> None:
    """Start the sciop development server"""
    from sciop.config import Config, get_config
    from sciop.main import main

    if config is None:
        cfg = get_config()
    else:
        config = Path(config)
        cfg = Config.load(config)

    if port is not None:
        cfg.server.port = port

    main(config=cfg)
