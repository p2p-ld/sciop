import click

from sciop.cli.generate import generate
from sciop.cli.maintain import maintain
from sciop.cli.start import start


@click.group(name="sciop")
@click.version_option(package_name="sciop")
def main() -> None:
    """Sciop CLI"""
    pass


def _main() -> None:
    main(max_content_width=100)


main.add_command(generate, "generate")
main.add_command(start, "start")
main.add_command(maintain, "maintain")
