import json
from collections import defaultdict

from sqlmodel import Session, select
from starlette.testclient import TestClient

from sciop.config import config
from sciop.models import DatasetRead, DatasetTagLink, DatasetURL, ExternalIdentifier
from sciop.services.markdown import render_markdown


def test_edit_unauthorized(client: TestClient, dataset, get_auth_header, account):
    """
    Any random joe schmoe off the street shouldn't be able to edit stuff
    """
    ds = dataset()
    patch = {"slug": "new-slug"}
    res = client.patch(config.api_prefix + f"/datasets/{ds.slug}", json=patch)
    assert res.status_code == 401

    acc = account(username="newbie")
    header = get_auth_header(username=acc.username)
    res = client.patch(config.api_prefix + f"/datasets/{ds.slug}", json=patch, headers=header)
    assert res.status_code == 401


def test_edit_scalars(client, dataset, admin_auth_header):
    """
    We can edit a dataset by providing some subset of its values as scalars
    """
    ds = dataset()
    original = json.loads(DatasetRead.model_validate(ds).model_dump_json())

    patch = {"slug": "new-slug", "description": "some different description"}

    patched = {**original, **patch}
    patched["description_html"] = render_markdown(patch["description"])
    res = client.patch(
        config.api_prefix + f"/datasets/{ds.slug}", json=patch, headers=admin_auth_header
    )
    assert res.status_code == 200
    res_json = res.json()
    assert len(res_json) == len(patched)
    assert all([res_json[k] == patched[k] for k, v in res_json.items() if k not in ("updated_at",)])


def test_edit_relations(client, dataset, admin_auth_header, session: Session):
    """
    We can edit multivalued relation fields with some reasonable interface
    """
    ds = dataset(
        external_identifiers=[
            {"type": "doi", "identifier": "10.1000/default"},
            {"type": "ark", "identifier": "whatever-an-ark-is"},
        ]
    )
    original = json.loads(DatasetRead.model_validate(ds).model_dump_json())
    session.expire(ds)

    # add and remove items
    new_tags = ["default", "newtag", "thirdtag"]
    new_ids = [
        {"type": "doi", "identifier": "10.1000/default"},
        {"type": "doi", "identifier": "10.1000/new-doi"},
    ]
    new_urls = ["https://example.com/1", "https://newurl.com/2"]
    patch = {"tags": new_tags, "external_identifiers": new_ids, "urls": new_urls}
    patched = {**original, **patch}
    assert patched["tags"] == new_tags
    assert patched["external_identifiers"] == new_ids
    assert patched["urls"] == new_urls

    res = client.patch(
        config.api_prefix + f"/datasets/{ds.slug}", json=patch, headers=admin_auth_header
    )
    assert res.status_code == 200
    res_json = res.json()
    assert len(res_json) == len(patched)
    assert all([res_json[k] == patched[k] for k, v in res_json.items() if k not in ("updated_at",)])
    # test subvals specifically
    for key in ("tags", "external_identifiers", "urls"):
        assert all([orig == new for orig, new in zip(res_json[key], patched[key])])

    # we did not create new items for the ones that already exist
    urls = session.exec(select(DatasetURL)).all()
    url_history = session.exec(select(DatasetURL.history_cls())).all()
    eids = session.exec(select(ExternalIdentifier)).all()
    eid_history = session.exec(select(ExternalIdentifier.history_cls())).all()
    tag_history = session.exec(select(DatasetTagLink.history_cls())).all()

    # we keep the deleted ones just dissociate them from the parent
    assert len(urls) == 3
    assert len([url for url in urls if url.url == "https://example.com/1"]) == 1
    assert [url for url in urls if url.url == "https://example.com/2"][0].dataset_id is None
    # 2 creations + 1 unchanged + 1 creation + 1 dissociation
    assert len(url_history) == 5
    history_map = defaultdict(list)
    for url in url_history:
        history_map[url.version_created_at].append(url)
    assert len(history_map) == 2
    latest = history_map[max(history_map.keys())]
    assert len(latest) == 3
    for url in latest:
        if url.url == "https://example.com/2":
            assert url.dataset_id is None
        else:
            assert url.dataset_id == 1

    # external ids - these are the same kind of model as urls, so we just check number
    assert len(eids) == 3
    assert len(eid_history) == 5

    # tags are forced to be unique so we don't need to check double creation,
    # but we should check on the history (and this is tested in the editable mixin tests)
    # 3 original + 2 new + 1 unchanged + 2 deleted == 8
    assert len(tag_history) == 8
