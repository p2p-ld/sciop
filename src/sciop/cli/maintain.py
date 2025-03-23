import click


@click.group("maintain")
def maintain() -> None:
    """sciop maintenance tasks"""
    pass


@maintain.group("search")
def search() -> None:
    """search maintenance tasks"""


@search.command("reindex")
def reindex() -> None:
    """drop search tables and reindex"""
    from sciop.db import get_engine
    from sciop.models.mixins import SearchableMixin

    engine = get_engine()

    for subcls in SearchableMixin.__subclasses__():
        click.echo(f"reindexing {subcls.__name__}")
        subcls.fts_rebuild(engine)
