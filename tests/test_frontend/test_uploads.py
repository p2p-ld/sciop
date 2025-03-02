import pytest


@pytest.mark.parametrize("use_hash", ["v1_infohash", "v2_infohash", "short_hash"])
def test_uploads_urls(use_hash, client, upload):
    """Uploads can be reached from their v1, v2, and short hashes"""
    ul = upload()
    hash = getattr(ul.torrent, use_hash)
    res = client.get(f"/uploads/{hash}")
    assert res.status_code == 200


def test_no_show_unapproved(account, upload, client):
    acc = account()
    ul = upload(account=acc, is_approved=False)
    res = client.get(f"/uploads/{ul.infohash}")
    assert res.status_code == 404


def test_no_show_removed(account, upload, client, session):
    acc = account()
    ul = upload(account=acc)
    infohash = ul.infohash
    ul.is_removed = True
    session.add(ul)
    session.commit()
    session.refresh(ul)

    res = client.get(f"/uploads/{infohash}")
    assert res.status_code == 404


def test_no_include_unapproved(dataset, upload, client):
    """Unapproved uploads are not included in dataset uploads lists"""
    ds = dataset()
    unapproved = upload(dataset_=ds, is_approved=False)
    approved = upload(dataset_=ds, is_approved=True)
    res = client.get("/datasets/default/uploads")
    assert res.status_code == 200
    assert unapproved.infohash not in res.text
    assert approved.infohash in res.text


def test_no_include_removed(dataset, upload, client, session):
    """Removed uploads are not included in dataset uploads lists"""
    ds = dataset()
    removed = upload(dataset_=ds, is_approved=True)
    approved = upload(dataset_=ds, is_approved=True)
    removed_infohash = removed.infohash
    approved_infohash = approved.infohash
    removed.is_removed = True
    session.add(removed)
    session.commit()

    res = client.get("/datasets/default/uploads")
    assert res.status_code == 200
    assert removed_infohash not in res.text
    assert approved_infohash in res.text
