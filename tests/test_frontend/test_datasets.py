def test_no_show_unapproved(client, dataset):
    ds_ = dataset(slug="unapproved", is_approved=False)
    res = client.get("/datasets/unapproved")
    assert res.status_code == 404


def test_no_show_removed(client, dataset):
    ds_ = dataset(slug="removed", is_approved=True, is_removed=True)
    res = client.get("/datasets/removed")
    assert res.status_code == 404


def test_no_include_unapproved(client, dataset):
    """Unapproved datasets don't show up on the datasets page"""
    approved = dataset(slug="approved", is_approved=True)
    ds_ = dataset(slug="unapproved", is_approved=False)
    assert not ds_.is_approved
    res = client.get("/datasets/search")
    items = res.json()["items"]
    assert len(items) == 1
    slugs = [i["slug"] for i in items]
    assert "unapproved" not in slugs
    assert "approved" in slugs


def test_include_unapproved_if_reviewer(client, dataset, reviewer, get_auth_header):
    """Unapproved datasets do show up on the datasets page to reviewers"""
    header = get_auth_header(username=reviewer.username)
    approved = dataset(slug="approved", is_approved=True)
    ds_ = dataset(slug="unapproved", is_approved=False)
    assert not ds_.is_approved
    res = client.get("/datasets/search", headers=header)
    items = res.json()["items"]
    assert len(items) == 2
    slugs = [i["slug"] for i in items]
    assert "unapproved" in slugs
    assert "approved" in slugs


def test_no_include_removed(client, dataset):
    """Removed datasets are not included on the datasets page"""
    approved = dataset(slug="approved", is_approved=True, is_removed=False)
    ds_ = dataset(slug="removed", is_approved=True, is_removed=True)
    assert ds_.is_removed
    res = client.get("/datasets/search")
    items = res.json()["items"]
    assert len(items) == 1
    slugs = [i["slug"] for i in items]
    assert "removed" not in slugs
    assert "approved" in slugs


def test_no_include_removed_if_reviewer(client, dataset, reviewer, get_auth_header):
    """Removed datasets are not included on the datasets page, even to reviewers"""
    header = get_auth_header(username=reviewer.username)
    approved = dataset(slug="approved", is_approved=True)
    ds_ = dataset(slug="removed", is_approved=True, is_removed=True)
    assert ds_.is_removed
    res = client.get("/datasets/search", headers=header)
    items = res.json()["items"]
    assert len(items) == 1
    slugs = [i["slug"] for i in items]
    assert "removed" not in slugs
    assert "approved" in slugs
