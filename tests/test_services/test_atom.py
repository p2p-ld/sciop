from datetime import UTC, datetime

import pytest
from sqlmodel import select

from sciop.config.services import UpdateFeed, UpdateFeedsConfig
from sciop.logging import init_logger
from sciop.models.atom import AtomFeed, AtomFeedEntry
from sciop.services.atom import _ensure_feeds, update_feeds

feed_template = """
<feed>
<generator uri="https://jekyllrb.com/" version="4.4.1">Jekyll</generator>
<link href="https://blog.sciop.net/feed.xml" rel="self" type="application/atom+xml"/>
<link href="https://blog.sciop.net/" rel="alternate" type="text/html"/>
<updated>{updated}</updated>
<id>https://blog.sciop.net/feed.xml</id>
<title type="html">SciOp The Blog</title>
<subtitle>SciOp: The Blog for SciOp: The Website</subtitle>
{entries}
</feed>
"""

entry_template = """
<entry>
<title type="html">{title}</title>
<link href="https://blog.sciop.net/{title}" rel="alternate" type="text/html" title="{title}"/>
<published>{timestamp}</published>
<updated>{timestamp}</updated>
<id>https://blog.sciop.net/{title}</id>
<author>
<name>sneakers</name>
<uri>https://example.com/sneakers</uri>
</author>
<summary type="html">
{summary}
</summary>
</entry>"""

entries = (
    {
        "title": "third",
        "timestamp": "2025-01-03T22:33:33+00:00",
        "summary": "this is the third post",
    },
    {
        "title": "second",
        "timestamp": "2025-01-02T22:22:22+00:00",
        "summary": "this is the second post",
    },
    {
        "title": "first",
        "timestamp": "2025-01-01T11:11:11+00:00",
        "summary": "this is the first post",
    },
)

formatted_entries = [
    entry_template.format(title=e["title"], timestamp=e["timestamp"], summary=e["summary"])
    for e in entries
]


@pytest.fixture()
def configure_feed(set_config) -> UpdateFeedsConfig:
    """Configure us for the test feed"""
    cfg = UpdateFeedsConfig(
        enabled=True,
        max_n_posts=2,
        feeds=[UpdateFeed(url="https://blog.sciop.net/feed.xml", name="sciop")],
    )
    set_config({"services.update_feeds": cfg})
    return cfg


def test_ensure_creates(session):
    """
    Create feeds specified in the config
    """
    feeds = [
        UpdateFeed(url="https://example.com/a", name="a"),
        UpdateFeed(url="https://example.com/b", name="b"),
    ]

    existing = session.exec(select(AtomFeed)).all()
    assert not existing

    logger = init_logger("jobs.update_atom_feed")
    _ensure_feeds(feeds, logger)

    existing = session.exec(select(AtomFeed).order_by(AtomFeed.url)).all()
    assert len(existing) == len(feeds)
    for expected, exists in zip(feeds, existing):
        assert str(expected.url) == exists.url
        assert expected.name == exists.name


def test_ensure_deletes(session):
    """
    Delete feeds that exist but are no longer specified in the config
    """
    feeds = [
        UpdateFeed(url="https://example.com/a", name="a"),
        UpdateFeed(url="https://example.com/b", name="b"),
    ]

    old = AtomFeed(url="https://example.com/c", name="c")
    old_url = old.url
    session.add(old)
    session.commit()

    logger = init_logger("jobs.update_atom_feed")
    _ensure_feeds(feeds, logger)

    existing = session.exec(select(AtomFeed).order_by(AtomFeed.url)).all()
    assert len(existing) == len(feeds)
    assert not any(f.url == old_url for f in existing)


@pytest.mark.asyncio
async def test_update_feed(session, configure_feed, httpx_mock):
    """
    Base case for updating a feed - on first config, fetch feed and add to db
    """
    expected_entries = entries[-2:]
    feed = feed_template.format(
        updated="2025-01-02T22:22:22+00:00", entries="\n".join(formatted_entries[-2:])
    )
    httpx_mock.add_response(url=str(configure_feed.feeds[0].url), text=feed)

    await update_feeds()

    db_feeds = session.exec(select(AtomFeed)).all()
    assert len(db_feeds) == 1
    got_feed = db_feeds[0]
    assert len(got_feed.entries) == 2
    got_entries = sorted(got_feed.entries, key=lambda e: e.updated, reverse=True)
    for got, expected in zip(got_entries, expected_entries):
        got: AtomFeedEntry
        assert str(got.link) == f"https://blog.sciop.net/{expected['title']}"
        assert str(got.title) == str(expected["title"])
        assert got.updated.replace(tzinfo=UTC) == datetime.fromisoformat(expected["timestamp"])
        assert got.summary == expected["summary"]


@pytest.mark.asyncio
async def test_no_update_when_unchanged(session, configure_feed, httpx_mock, capsys):
    """
    If a feed has not changed since the last time,
    Don't try and update our db objects
    """
    feed = feed_template.format(
        updated="2025-01-02T22:22:22+00:00", entries="\n".join(formatted_entries[-2:])
    )
    httpx_mock.add_response(url=str(configure_feed.feeds[0].url), text=feed)

    # do first update
    await update_feeds()

    # mess up the entries to make sure we don't replace it
    # wrong... in this case... is good
    db_entries = session.exec(select(AtomFeedEntry)).all()
    for e in db_entries:
        e.summary = "WRONG"
        session.add(e)
    session.commit()

    # do second update, we should get the feed but do nothing with it
    httpx_mock.add_response(url=str(configure_feed.feeds[0].url), text=feed)

    await update_feeds()

    db_entries = session.exec(select(AtomFeedEntry)).all()
    assert all(e.summary == "WRONG" for e in db_entries)
    stdout = capsys.readouterr().out
    assert "unchanged since last update" in stdout


@pytest.mark.asyncio
async def test_replace_feed_items(session, configure_feed, httpx_mock):
    """
    When we exceed the max number of items, we should remove old items
    """
    feed = feed_template.format(
        updated="2025-01-02T22:22:22+00:00", entries="\n".join(formatted_entries[-2:])
    )
    httpx_mock.add_response(url=str(configure_feed.feeds[0].url), text=feed)

    # do first update with two items
    await update_feeds()

    three_feed = feed_template.format(
        updated="2025-01-03T22:33:33+00:00", entries="\n".join(formatted_entries)
    )
    httpx_mock.add_response(url=str(configure_feed.feeds[0].url), text=three_feed)

    # update again with three items in the feed
    await update_feeds()

    db_entries = session.exec(select(AtomFeedEntry)).all()
    assert len(db_entries) == 2
    assert any([e.title == "third" for e in db_entries])
    assert not any([e.title == "first" for e in db_entries])
