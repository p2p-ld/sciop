import sys
from pathlib import Path

import click

from sciop.cli.common import config_option
from sciop.services import build_docs


@click.group("docs")
def docs() -> None:
    """Manage sciop documentation"""
    pass


@docs.command("build")
@config_option
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    help="Path to output. If not passed, src/sciop/docs",
    default=None,
)
def docs_build(config: Path | None = None, output: Path | None = None) -> None:
    """
    Build the sciop docs.
    """
    click.echo("Building docs")
    written_to = build_docs(config, output)
    if written_to:
        click.echo(f"Docs built to {written_to}")
    else:
        click.echo("Failed to build docs")
        sys.exit(1)
