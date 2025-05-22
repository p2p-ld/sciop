from typing import Optional

import click


@click.command()
@click.option("--port", required=False, type=int)
def start(port: Optional[int] = None) -> None:
    """Start the sciop development server"""
    from sciop.config import config
    from sciop.main import main

    if port is not None:
        config.server.port = port

    main(config=config)
