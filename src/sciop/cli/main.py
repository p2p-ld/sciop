import click

from sciop.cli.maintain import maintain
from sciop.cli.start import start


@click.group(name="sciop")
@click.version_option(package_name="sciop")
def main() -> None:
    """Sciop CLI"""
    pass


main.add_command(start, "start")
main.add_command(maintain, "maintain")
