"""
Update atom feeds used for "whats new" section on the homepage.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import httpx
from bs4 import BeautifulSoup
from sqlmodel import select

from sciop.config import get_config
from sciop.db import get_session
from sciop.logging import init_logger
from sciop.models import AtomFeed, AtomFeedEntry

if TYPE_CHECKING:
    from logging import Logger

    from sciop.config.services import UpdateFeed


async def update_feeds() -> None:
    """
    Top-level service function for updating feeds.

    - Ensure that configured feeds are created and exist in the db,
    - Remove any feeds that exist but have been removed
    - Update each configured feed
    """
    logger = init_logger("jobs.update_atom_feed")

    cfg = get_config()
    expected_feeds = cfg.services.update_feeds.feeds
    if not expected_feeds:
        logger.debug("No feeds configured, not updating")
        return
    _ensure_feeds(expected_feeds, logger)
    logger.info("Updating atom feeds")
    for feed in expected_feeds:
        # do serially because this is not a time-sensitive operation,
        # and we don't want to encourage db write locks to hold each other.
        try:
            await update_atom_feed(str(feed.url), cfg.services.update_feeds.max_n_posts)
        except (httpx.HTTPStatusError, httpx.TimeoutException) as e:
            logger.warning("HTTP Error updating atom feed %s: %s", feed.url, e)
        except Exception:
            # catch and log rather than raising, since we want to try updating all feeds.
            logger.exception("Unhandled error updating atom feed %s", feed.url)


def _ensure_feeds(expected_feeds: list[UpdateFeed], logger: Logger) -> None:
    """
    Ensure that the feeds in the database match those in the configuration
    """
    feed_map = {str(f.url): f for f in expected_feeds}

    with get_session() as session:
        feeds = session.exec(select(AtomFeed)).all()
        # delete any removed feeds, update name if changed
        for f in feeds:
            if f.url not in feed_map:
                logger.debug("Deleting removed feed %s", f.url)
                session.delete(f)
            elif f.name != feed_map[f.url].name:
                logger.debug(
                    "Feed with url %s changed name from %s to %s",
                    f.url,
                    f.name,
                    feed_map[f.url].name,
                )
                f.name = feed_map[f.url].name
                session.add(f)

        # create new feeds that don't exist
        to_create = set(feed_map.keys()) - {str(f.url) for f in feeds}
        for new_url in to_create:
            logger.debug(
                "Creating new feed from config\nurl: %s\nname: %s", new_url, feed_map[new_url].name
            )
            new_feed = AtomFeed(url=new_url, name=feed_map[new_url].name)
            session.add(new_feed)
        session.commit()


async def update_atom_feed(url: str, max_items: int = 10) -> None:
    """
    Update an atom feed
    - Fetch the feed, if no new updates since last time, return
    - Load any existing items in the feed
    - Update them as necessary
    - Prune old entries according to the max length

    This is cheap enough with normal max items that we don't worry about
    preserving existing entries and just clear and remake them every time we update

    Raises:
        httpx.HTTPStatusError if the feed could not be fetched
    """
    cfg = get_config()
    logger = init_logger("jobs.update_atom_feed")
    logger.debug("%s - updating atom feed", url)

    async with httpx.AsyncClient(headers={"User-Agent": cfg.server.user_agent}) as client:
        res = await client.get(url, timeout=cfg.server.default_timeout)

    res.raise_for_status()
    soup = BeautifulSoup(res.text, "xml")
    feed_updated = datetime.fromisoformat(
        soup.select_one("feed > updated").text.strip()
    ).astimezone(UTC)
    with get_session() as session:
        existing_feed: AtomFeed | None = session.exec(
            select(AtomFeed).where(AtomFeed.url == url)
        ).first()

    if (
        existing_feed
        and existing_feed.updated_at is not None
        and feed_updated <= existing_feed.updated_at.replace(tzinfo=UTC)
    ):
        logger.debug("%s - Feed unchanged since last update, not updating items", url)
        return

    entries = soup.select("feed > entry")
    entries = sorted(entries, key=lambda e: e.select_one("updated").text.strip(), reverse=True)
    if len(entries) > max_items:
        entries = entries[:max_items]

    with get_session() as session:
        if existing_feed is None:
            existing_feed = AtomFeed(url=url, updated_at=feed_updated)
        else:
            existing_feed = session.merge(existing_feed)
            existing_feed.updated_at = feed_updated

        existing_feed.entries = [AtomFeedEntry.from_soup(e) for e in entries]
        session.add(existing_feed)
        session.commit()

    logger.debug("%s - atom feed updated successfully", url)
