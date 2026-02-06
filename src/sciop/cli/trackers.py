"""
Manage scraped trackers
"""

from typing import TYPE_CHECKING, Sequence

import click
from rich.console import Console
from rich.table import Table
from sqlmodel import select

from sciop.db import get_session

if TYPE_CHECKING:
    from sciop.models import Tracker


@click.group("trackers")
def trackers() -> None:
    """
    Manage scraped trackers
    """
    pass


@trackers.command("show")
def show_trackers() -> None:
    """
    show details of scraped trackers
    """
    from sciop.models import Tracker

    with get_session() as session:
        trackers = session.exec(select(Tracker)).all()
        # sort by n torrents
        trackers = sorted(trackers, key=lambda tracker: len(tracker.torrent_links), reverse=True)

    table = _tracker_table(trackers)
    Console().print(table)


@trackers.command("clear")
@click.option(
    "--url",
    "-u",
    type=click.STRING,
    multiple=True,
    help="Announce url of tracker to clear. If not provided, clears all trackers.",
)
def clear_tracker_backoff(url: tuple[str] | None = None) -> None:
    """
    Clear error counts and backoff times to allow trackers to be scraped again
    """
    from sciop.models import Tracker

    with get_session() as session:
        sel = select(Tracker)
        if url:
            sel = sel.where(Tracker.announce_url.in_(url))
        trackers = session.exec(sel).all()
        for tracker in trackers:
            tracker.clear_backoff()
        session.commit()
        for tracker in trackers:
            session.refresh(tracker)

        table = _tracker_table(trackers)
    Console().print(table)


def _tracker_table(trackers: Sequence["Tracker"]) -> Table:
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("URL")
    table.add_column("# Torrents")
    table.add_column("Last Scraped At")
    table.add_column("Next Scrape")
    table.add_column("# Errors")
    table.add_column("Error")

    for t in trackers:
        table.add_row(
            t.announce_url,
            str(len(t.torrent_links)),
            t.last_scraped_at.isoformat() if t.last_scraped_at else "-",
            t.next_scrape_after.isoformat() if t.next_scrape_after else "-",
            str(t.n_errors),
            str(t.error_type) if t.error_type else "",
        )
    return table
