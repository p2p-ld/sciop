import click

from sciop.cli.config import cli_config
from sciop.cli.docs import docs
from sciop.cli.generate import generate
from sciop.cli.maintain import maintain
from sciop.cli.start import start
from sciop.cli.trackers import trackers


@click.group(name="sciop")
@click.version_option(package_name="sciop")
def main() -> None:
    """Sciop CLI"""
    pass


def _main() -> None:
    main(max_content_width=100)


main.add_command(cli_config, "config")
main.add_command(docs, "docs")
main.add_command(generate, "generate")
main.add_command(start, "start")
main.add_command(maintain, "maintain")
main.add_command(trackers, "trackers")
