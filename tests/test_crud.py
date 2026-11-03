from copy import deepcopy

import pytest
from sqlmodel import select

from sciop import crud
from sciop.models import (
    URL,
    DatasetClaim,
    DatasetCreate,
    DatasetURLLink,
    Tag,
    TorrentFileCreate,
    Tracker,
)
from sciop.testing.fabricators import default_dataset, default_torrentfile


def test_create_dataset_tags(session):
    """
    Creating a new dataset correctly uses existing tags and makes new ones
    """
    # FIXME: implement transactional tests...
    existing_tag = session.exec(select(Tag).filter(Tag.tag == "existing")).first()
    if not existing_tag:
        existing_tag = Tag(tag="existing")
        session.add(existing_tag)
        session.commit()
        session.refresh(existing_tag)

    a = default_dataset()
    a["tags"].append("existing")
    a["tags"].append("a-new-one")
    a["title"] = "Dataset A"
    a["slug"] = "dataset-a"

    b = default_dataset()
    b["tags"].append("existing")
    b["tags"].append("another-new-one")
    b["title"] = "Dataset B"
    b["slug"] = "dataset-B"

    if dataset_a := crud.get_dataset(session=session, dataset_slug="dataset-a"):
        session.delete(dataset_a)
    if dataset_b := crud.get_dataset(session=session, dataset_slug="dataset-b"):
        session.delete(dataset_b)
    session.commit()

    dataset_a = crud.create_dataset(session=session, dataset_create=DatasetCreate(**a))
    dataset_b = crud.create_dataset(session=session, dataset_create=DatasetCreate(**b))

    existing_a = [tag for tag in dataset_a.tags if tag.tag == "existing"][0]
    existing_b = [tag for tag in dataset_b.tags if tag.tag == "existing"][0]

    assert existing_a.tag_id == existing_b.tag_id == existing_tag.tag_id

    assert len([tag for tag in dataset_a.tags if tag.tag == "a-new-one"]) == 1
    assert len([tag for tag in dataset_b.tags if tag.tag == "another-new-one"]) == 1


def test_urls_shared(session, dataset, upload):
    """
    Datasets and uploads with the same url share a single url row
    """
    url = "https://example.com/shared"

    ds_a = dataset(slug="dataset-a", urls=[url, "https://example.com/a"])
    ds_b = dataset(slug="dataset-b", urls=[url])
    ul = upload(dataset_=ds_a, urls=[url])

    shared = session.exec(select(URL).where(URL.url == url)).one()
    assert {ds.slug for ds in shared.datasets} == {ds_a.slug, ds_b.slug}
    assert shared.uploads == [ul]
    assert [url.url for url in ds_a.urls] == ["https://example.com/a", url]


def test_assign_urls(session, dataset):
    """
    Assigning urls replaces an item's urls, dropping duplicates and reusing existing url rows,
    without touching other items' links
    """
    existing = URL(url="https://example.com/existing")
    session.add(existing)
    session.commit()
    other = dataset(slug="other", urls=["https://example.com/existing"])
    ds = dataset(slug="target", urls=["https://example.com/old"])

    ds.urls = ["https://example.com/new", existing, "https://example.com/new"]
    session.add(ds)
    session.flush()
    # urls are readable after a flush, before the commit
    assert {url.url for url in ds.urls} == {
        "https://example.com/new",
        "https://example.com/existing",
    }
    session.commit()

    assert existing in ds.urls
    assert [url.url for url in other.urls] == ["https://example.com/existing"]
    assert len(session.exec(select(URL).where(URL.url == "https://example.com/new")).all()) == 1

    ds.urls = []
    session.add(ds)
    session.commit()
    assert ds.urls == []
    assert [url.url for url in other.urls] == ["https://example.com/existing"]


def test_reassign_urls_keeps_existing_links(session, dataset):
    """
    Reassigning urls keeps the links that are still in the list,
    removes the ones that aren't, and adds new ones
    """
    a, b, c = "https://example.com/a", "https://example.com/b", "https://example.com/c"
    ds = dataset(urls=[a, b])

    def links() -> dict[str, DatasetURLLink]:
        rows = session.exec(
            select(DatasetURLLink, URL)
            .join(URL, URL.url_id == DatasetURLLink.url_id)
            .where(DatasetURLLink.dataset_id == ds.dataset_id)
        ).all()
        return {url.url: link for link, url in rows}

    created_b = links()[b].created_at

    ds.urls = [b, c]
    session.add(ds)
    session.commit()
    after = links()
    assert sorted(after) == [b, c]
    assert after[b].created_at == created_b
    assert after[b].updated_at > created_b

    # saving the same list again keeps every link
    ds.urls = [b, c]
    session.add(ds)
    session.commit()
    assert sorted(links()) == [b, c]
    assert links()[b].created_at == created_b


def test_reassign_url_statuses(session, upload):
    """
    Reassigning an upload's urls updates the statuses of links that are kept,
    including clearing them when a url is given without one
    """
    a, b = "https://example.com/a", "https://example.com/b"
    ul = upload(urls=[{"url": a, "status": 200}, {"url": b, "status": 404}])
    assert {link.url.url: link.status for link in ul.urls} == {a: 200, b: 404}

    ul.urls = [{"url": a, "status": 301}, b]
    session.add(ul)
    session.commit()
    assert {link.url.url: link.status for link in ul.urls} == {a: 301, b: None}


def test_urls_partial_changes_raise(session, dataset):
    """
    urls can only be assigned as a whole list,
    since appending to or removing from the collection would silently not be saved
    """
    ds = dataset(urls=["https://example.com/a", "https://example.com/b"])
    first = ds.urls[0]

    changes = [
        lambda: ds.urls.append(URL(url="https://example.com/c")),
        lambda: ds.urls.extend([URL(url="https://example.com/c")]),
        lambda: ds.urls.remove(first),
        lambda: ds.urls.__delitem__(0),
        lambda: ds.urls.__iadd__([URL(url="https://example.com/c")]),
    ]
    for change in changes:
        with pytest.raises(TypeError, match="assigned as a whole list"):
            change()
    assert [url.url for url in ds.urls] == ["https://example.com/a", "https://example.com/b"]

    # replacing a loaded collection removes its old items without raising
    ds.urls = ["https://example.com/c"]
    session.add(ds)
    session.commit()
    assert [url.url for url in ds.urls] == ["https://example.com/c"]


def test_create_torrent_with_trackers(session, infohashes, uploader):
    torrent_a = deepcopy(default_torrentfile())
    torrent_b = deepcopy(default_torrentfile())

    a_tracker = "udp://uniquetracker.com"
    b_tracker = "udp://didnt-think-ahead-about-uniquetracker2.com"
    shared = "udp://shared.com"

    torrent_a["announce_urls"].append(shared)
    torrent_a["announce_urls"].append(a_tracker)
    torrent_b["announce_urls"].append(shared)
    torrent_b["announce_urls"].append(b_tracker)
    torrent_a.update(infohashes())
    torrent_b.update(infohashes())

    a = crud.create_torrent(
        session=session, created_torrent=TorrentFileCreate(**torrent_a), account=uploader
    )
    b = crud.create_torrent(
        session=session, created_torrent=TorrentFileCreate(**torrent_b), account=uploader
    )

    trackers = session.exec(select(Tracker)).all()
    assert len(trackers) == len(set(torrent_a["announce_urls"]) | set(torrent_b["announce_urls"]))
    assert len(a.tracker_links) == len(torrent_a["announce_urls"])
    assert len(b.tracker_links) == len(torrent_b["announce_urls"])

    # use the same tracker object for shared
    assert a.trackers[shared].tracker_id == b.trackers[shared].tracker_id
    assert a_tracker in a.trackers
    assert b_tracker not in a.trackers
    assert b_tracker in b.trackers
    assert a_tracker not in b.trackers


def test_get_dataset_claims(session, account, dataset):
    """get JUST the parent dataset claims"""
    ds = dataset(
        slug="test", parts=[{"part_slug": "part-1"}, {"part_slug": "part-2"}], is_approved=True
    )
    acct = account()
    claims = [
        DatasetClaim(account=acct, dataset=ds, status="in_progress"),
        DatasetClaim(account=acct, dataset=ds, dataset_part=ds.parts[0], status="completed"),
        DatasetClaim(account=acct, dataset=ds, dataset_part=ds.parts[1], status="completed"),
    ]
    for c in claims:
        session.add(c)
    session.commit()

    claim = crud.get_claims(
        session=session, username=acct.username, dataset_slug="test", part_slugs=None
    )
    assert len(claim) == 1
    assert claim[0].dataset_part is None


def test_get_dataset_part_claims(session, account, dataset):
    """get JUST the dataset part claims"""
    ds = dataset(
        slug="test", parts=[{"part_slug": "part-1"}, {"part_slug": "part-2"}], is_approved=True
    )
    acct = account()
    claims = [
        DatasetClaim(account=acct, dataset=ds, status="in_progress"),
        DatasetClaim(account=acct, dataset=ds, dataset_part=ds.parts[0], status="completed"),
        DatasetClaim(account=acct, dataset=ds, dataset_part=ds.parts[1], status="completed"),
    ]
    for c in claims:
        session.add(c)
    session.commit()

    claim = crud.get_claims(
        session=session,
        username=acct.username,
        dataset_slug="test",
        part_slugs=["part-1", "part-2"],
    )
    assert len(claim) == 2
    got_slugs = [c.dataset_part.part_slug if c.dataset_part else "" for c in claim]
    assert sorted(got_slugs) == sorted(["part-1", "part-2"])


def test_get_all_dataset_claims(session, account, dataset):
    """get ALL the dataset claims"""
    ds = dataset(
        slug="test", parts=[{"part_slug": "part-1"}, {"part_slug": "part-2"}], is_approved=True
    )
    acct = account()
    claims = [
        DatasetClaim(account=acct, dataset=ds, status="in_progress"),
        DatasetClaim(account=acct, dataset=ds, dataset_part=ds.parts[0], status="completed"),
        DatasetClaim(account=acct, dataset=ds, dataset_part=ds.parts[1], status="completed"),
    ]
    for c in claims:
        session.add(c)
    session.commit()

    claim = crud.get_claims(
        session=session, username=acct.username, dataset_slug="test", part_slugs=True
    )
    assert len(claim) == 3
    got_slugs = [c.dataset_part.part_slug if c.dataset_part else "" for c in claim]
    assert sorted(got_slugs) == sorted(["", "part-1", "part-2"])


@pytest.mark.parametrize("parts", [None, ["part-1"]])
def test_upload_clears_claims(session, account, dataset, upload, parts: None | list[str]):
    """Making an upload clears any existing dataset claims"""
    ds = dataset(
        slug="test", parts=[{"part_slug": "part-1"}, {"part_slug": "part-2"}], is_approved=True
    )
    acct = account()
    claims = [
        DatasetClaim(account=acct, dataset=ds, status="in_progress"),
        DatasetClaim(account=acct, dataset=ds, dataset_part=ds.parts[0], status="completed"),
        DatasetClaim(account=acct, dataset=ds, dataset_part=ds.parts[1], status="completed"),
    ]
    for c in claims:
        session.add(c)
    session.commit()

    ul = upload(
        dataset_=ds,
        part_slugs=parts,
        account_=acct,
    )

    claim = crud.get_claims(
        session=session, username=acct.username, dataset_slug="test", part_slugs=True
    )
    assert len(claim) == 2
    got_slugs = sorted([c.dataset_part.part_slug if c.dataset_part else "" for c in claim])

    if parts:
        assert got_slugs == ["", "part-2"]
    else:
        assert got_slugs == ["part-1", "part-2"]
