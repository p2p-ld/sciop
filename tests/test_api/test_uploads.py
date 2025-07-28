from pathlib import Path
from typing import Callable as C

import pytest
from sqlmodel import Session
from torrent_models import Torrent

from sciop.config import get_config
from sciop.models import Account, Dataset, DatasetPart


@pytest.mark.parametrize("infohash_type", ["v1_infohash", "v2_infohash"])
def test_upload(
    dataset: C[..., Dataset],
    torrent: C[..., Torrent],
    client,
    uploader: Account,
    get_auth_header,
    infohash_type: str,
    tmp_path: Path,
) -> None:
    """We can create an upload!"""
    if infohash_type == "v2_infohash":
        pytest.skip("V2 support not implemented")
    ds = dataset(slug="test-upload", is_approved=True)

    header = get_auth_header(uploader.username)
    torrent_ = torrent()
    tfile = tmp_path / "test.torrent"
    torrent_.write(tfile)

    with open(tfile, "rb") as f:
        response = client.post(
            get_config().api_prefix + "/torrents", headers=header, files={"file": f}
        )
    response.raise_for_status()

    upload_create = {
        "infohash": response.json().get(infohash_type),
        "dataset_slug": ds.slug,
        "method": "By downloading it",
        "description": "It is an upload",
    }
    response = client.post(get_config().api_prefix + "/uploads", headers=header, json=upload_create)
    response.raise_for_status()
    created = response.json()
    assert created["method"] == upload_create["method"]
    assert created["description"] == upload_create["description"]
    assert created["torrent"][infohash_type] == upload_create["infohash"]
    assert created["dataset"] == ds.slug
    assert created["account"] == uploader.username


@pytest.mark.parametrize("part_slugs", (["part-1"], ["part-2", "part-3"]))
def test_upload_dataset_parts(
    dataset: C[..., Dataset],
    torrent: C[..., Torrent],
    client,
    uploader: Account,
    get_auth_header,
    tmp_path: Path,
    session: Session,
    part_slugs: list[str],
) -> None:
    """We can create an upload!"""
    ds = dataset(slug="test-upload", is_approved=True)
    ds.parts = [DatasetPart(part_slug=slug) for slug in part_slugs]
    session.add(ds)
    session.commit()

    header = get_auth_header(uploader.username)
    torrent_ = torrent()
    tfile = tmp_path / "test.torrent"
    torrent_.write(tfile)

    with open(tfile, "rb") as f:
        response = client.post(
            get_config().api_prefix + "/torrents", headers=header, files={"file": f}
        )
    response.raise_for_status()

    upload_create = {
        "infohash": response.json().get("v1_infohash"),
        "dataset_slug": ds.slug,
        "part_slugs": part_slugs,
        "method": "By downloading it",
        "description": "It is an upload",
    }
    response = client.post(get_config().api_prefix + "/uploads", headers=header, json=upload_create)
    response.raise_for_status()
    created = response.json()
    assert created["method"] == upload_create["method"]
    assert created["description"] == upload_create["description"]
    assert created["torrent"]["v1_infohash"] == upload_create["infohash"]
    assert created["dataset"] == ds.slug
    assert created["dataset_parts"] == part_slugs
