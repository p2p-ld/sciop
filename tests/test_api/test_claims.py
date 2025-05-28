import pytest

from sciop.config import get_config
from sciop.models import DatasetPart


def test_next_claim(dataset, client, account, upload, get_auth_header, session, set_config):
    """
    Getting the next claim should give us the next unclaimed dataset part,
    and claim it for ourselves!
    """
    set_config(enable_versions=False)
    acct = account(username="claimer")
    ds = dataset(slug="claimed")

    part_slugs = ("a", "b", "c")
    parts = {slug: DatasetPart(part_slug=slug, dataset=ds, is_approved=True) for slug in part_slugs}
    for part in parts.values():
        session.add(part)

    # one of them has an upload and shouldn't be present!
    ul = upload(dataset_=ds)
    ul.dataset_parts = [parts["b"]]
    session.add(ul)
    session.commit()

    header = get_auth_header("claimer")

    url = get_config().api_prefix + "/claims/claimed/next"
    for slug in ("a", "c"):
        res = client.post(url, headers=header)
        assert res.status_code == 200
        data = res.json()
        assert data["dataset_part"] == slug
        assert data["status"] == "in_progress"
        assert data["account"] == "claimer"

    # after they're all claimed (by us!) we should get a 404
    res = client.post(url, headers=header)
    assert res.status_code == 404


@pytest.mark.skip("TODO")
def test_get_claims():
    """Show all active claims"""
    pass


@pytest.mark.skip("TODO")
def test_get_dataset_claims():
    """Show all active dataset claims"""
    pass


@pytest.mark.skip("TODO")
def test_get_dataset_part_claims():
    """Show all active dataset part claims"""
    pass


@pytest.mark.skip("TODO")
def test_create_dataset_claim():
    """POSTing to a dataset claim makes one"""
    pass


@pytest.mark.skip("TODO")
def test_update_dataset_claim():
    """POSTing to a dataset claim that already exist updates it"""
    pass


@pytest.mark.skip("TODO")
def test_delete_dataset_claim():
    """DELETEing to a dataset claim that already exist deletes it"""
    pass


@pytest.mark.skip("TODO")
def test_create_dataset_part_claim():
    """POSTing to a dataset part claim makes one"""


@pytest.mark.skip("TODO")
def test_update_dataset_part_claim():
    """POSTing to a dataset part claim that already exist updates it"""
    pass


@pytest.mark.skip("TODO")
def test_delete_dataset_part_claim():
    """DELETINGing to a dataset part claim deletes it"""
    pass


@pytest.mark.skip("TODO")
def test_uploading_clears_claims():
    """Uploading to a dataset and dataset part part should clear our claims"""
    pass
