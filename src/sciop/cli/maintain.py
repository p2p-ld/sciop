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


@maintain.group("webseeds")
def webseeds() -> None:
    """
    Maintain externally added webseeds
    """


@webseeds.command("validate")
@click.option(
    "-s",
    "--status",
    type=click.Choice(["error", "queued"]),
    default="queued",
    show_default=True,
    help="Which type of webseeds to validate - "
    "queued webseeds that have not been validated, "
    "or errored webseeds that had a previous failed attempt at validation",
)
def validate(status: str = "queued") -> None:
    """
    Validate webseeds that are marked as queued but were not validated.

    This is necessary due to the way that the queueing system (currently) works -
    queued jobs are not maintained in the DB, but are instead kept in the
    queue of the process/thread pool executor.

    So if the instance crashes, the webseeds are marked as queued and never run.
    """
    from datetime import UTC, datetime, timedelta

    from anyio import from_thread
    from rich import print as rprint
    from sqlalchemy.orm import joinedload
    from sqlmodel import select
    from tqdm import tqdm

    from sciop.db import get_session
    from sciop.models import Webseed
    from sciop.services import validate_webseed_service

    with get_session() as session:
        queued = session.exec(
            select(Webseed)
            .options(joinedload(Webseed.torrent))
            .where(
                Webseed.status == status,
                Webseed.created_at <= datetime.now(UTC) - timedelta(minutes=1),
            )
        ).all()

    results = []
    with from_thread.start_blocking_portal() as portal:
        for ws in tqdm(queued):
            # run them one by one because each call makes a lot of requests,
            # and running all at once had a tendency to timeout.
            res = portal.call(validate_webseed_service, ws.torrent.infohash, ws.url)
            results.append(res)

    rprint("Webseed validation results:")
    rprint(results)
