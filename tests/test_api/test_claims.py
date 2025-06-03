import pytest

from sciop.config import get_config
from sciop.models import Dataset, DatasetPart


@pytest.fixture()
def claim_items(
    dataset, account, set_config, session, get_auth_header
) -> tuple[Dataset, dict[str, DatasetPart], str]:
    """Make items to test claims against"""
    set_config(enable_versions=False)
    acct = account(username="claimer")
    ds = dataset(slug="claimed")

    part_slugs = ("a", "b", "c")
    parts = {slug: DatasetPart(part_slug=slug, dataset=ds, is_approved=True) for slug in part_slugs}
    for part in parts.values():
        session.add(part)

    ds2 = dataset(slug="claimed-second")

    part_slugs2 = ("d", "e", "f")
    parts2 = {
        slug: DatasetPart(part_slug=slug, dataset=ds2, is_approved=True) for slug in part_slugs2
    }
    for part in parts2.values():
        session.add(part)

    session.commit()
    session.refresh(ds)
    header = get_auth_header("claimer")

    return ds, parts, header


def test_next_claim(claim_items, client, upload, get_auth_header, session):
    """
    Getting the next claim should give us the next unclaimed dataset part,
    and claim it for ourselves!
    """
    ds, parts, header = claim_items

    # one of them has an upload and shouldn't be present!
    ul = upload(dataset_=ds)
    ul.dataset_parts = [parts["b"]]
    session.add(ul)
    session.commit()

    url = get_config().api_prefix + "/claims/datasets/claimed/next"
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


def test_get_claims(claim_items, client, dataset, session):
    """Show all active claims"""
    ds, parts, header = claim_items

    url = get_config().api_prefix + "/claims/datasets/claimed/next"
    for _ in ("a", "b", "c"):
        res = client.post(url, headers=header)
        assert res.status_code == 200

    res = client.post(
        get_config().api_prefix + "/claims/datasets/claimed-second/next", headers=header
    )
    res.raise_for_status()

    claims = client.get(get_config().api_prefix + "/claims/")
    claims.raise_for_status()
    claims = claims.json()
    assert len(claims["items"]) == 4
    assert all([claim["account"] == "claimer"] for claim in claims["items"])
    assert set(claim["dataset"] for claim in claims["items"]) == {"claimed", "claimed-second"}


def test_get_dataset_claims(client, claim_items):
    """Show all active dataset claims"""
    ds, parts, header = claim_items

    url = get_config().api_prefix + "/claims/datasets/claimed/next"
    for _ in ("a", "b", "c"):
        res = client.post(url, headers=header)
        assert res.status_code == 200

    claims = client.get(get_config().api_prefix + "/claims/datasets/claimed")
    claims.raise_for_status()
    claims = claims.json()
    assert len(claims["items"]) == 3


def test_get_create_dataset_part_claims(client, claim_items, account, get_auth_header):
    """Show all active dataset part claims"""
    ds, parts, header = claim_items

    acct2 = account(username="claimer-two")
    header2 = get_auth_header("claimer-two")

    url = get_config().api_prefix + "/claims/datasets/claimed/parts/a"
    client.post(url, headers=header, json={"claim_status": "in_progress"})
    client.post(url, headers=header2, json={"claim_status": "in_progress"})

    claims = client.get(get_config().api_prefix + "/claims/datasets/claimed/parts/a")
    claims.raise_for_status()
    claims = claims.json()
    assert len(claims["items"]) == 2
    assert sorted([claim["account"] for claim in claims["items"]]) == ["claimer", "claimer-two"]


def test_update_dataset_part_claim(client, claim_items):
    """POSTing to a dataset part claim that already exist updates it"""
    ds, parts, header = claim_items
    url = get_config().api_prefix + "/claims/datasets/claimed/parts/a"
    client.post(url, headers=header, json={"status": "in_progress"})
    # we already know that works
    url = get_config().api_prefix + "/claims/datasets/claimed/parts/a"
    client.post(url, headers=header, json={"status": "completed"})
    claims = client.get(get_config().api_prefix + "/claims/datasets/claimed/parts/a")
    claims.raise_for_status()
    claims = claims.json()
    assert len(claims["items"]) == 1
    assert claims["items"][0]["status"] == "completed"


def test_delete_dataset_part_claim(client, claim_items):
    """DELETINGing to a dataset part claim deletes it"""
    ds, parts, header = claim_items
    url = get_config().api_prefix + "/claims/datasets/claimed/parts/a"
    client.post(url, headers=header, json={"claim_status": "in_progress"})
    res = client.delete(
        get_config().api_prefix + "/claims/datasets/claimed/parts/a", headers=header
    )
    assert res.status_code == 200
    claims = client.get(get_config().api_prefix + "/claims/datasets/claimed/parts/a")
    claims.raise_for_status()
    claims = claims.json()
    assert len(claims["items"]) == 0


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
def test_uploading_clears_claims():
    """Uploading to a dataset and dataset part part should clear our claims"""
    pass
