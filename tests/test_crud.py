from copy import deepcopy

import pytest
from sqlmodel import select

from sciop import crud
from sciop.models import DatasetClaim, DatasetCreate, Tag, TorrentFileCreate, Tracker
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
