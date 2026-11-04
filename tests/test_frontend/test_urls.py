def test_url_search_groups(dataset, upload, client):
    """
    URL search lists matching urls with the visible datasets and uploads that link to them
    """
    shared = "https://example.com/shared"
    ds = dataset(slug="has-url", urls=[shared])
    dataset(slug="hidden-url", urls=[shared], is_approved=False)
    dataset(slug="other-url", urls=["https://other.com/"])
    ul = upload(dataset_=ds, urls=[shared])
    hidden_ul = upload(dataset_=ds, urls=[shared], is_approved=False)

    res = client.get("/urls/search?query=example", headers={"HX-Request": "true"})
    assert res.status_code == 200
    assert shared in res.text
    assert "other.com" not in res.text
    assert "dataset-collapsible-has-url" in res.text
    assert "hidden-url" not in res.text
    assert f"upload-collapsible-{ul.infohash}" in res.text
    assert hidden_ul.infohash not in res.text


def test_url_search_statuses(dataset, upload, client):
    """Each upload under a url shows the status the url returned for that upload"""
    url = "https://example.com/status"
    ds = dataset(slug="has-url")
    ul_ok = upload(dataset_=ds, urls=[{"url": url, "status": 200}])
    ul_gone = upload(dataset_=ds, urls=[{"url": url, "status": 410}])
    ul_unknown = upload(dataset_=ds, urls=[url])

    res = client.get("/urls/search?query=example", headers={"HX-Request": "true"})
    assert res.status_code == 200
    rows = {
        ul.infohash: res.text.split(f'id="upload-collapsible-{ul.infohash}"')[1].split(
            "</details>"
        )[0]
        for ul in (ul_ok, ul_gone, ul_unknown)
    }
    assert 'class="status-tag status-2xx"' in rows[ul_ok.infohash]
    assert 'class="status-tag status-4xx"' in rows[ul_gone.infohash]
    assert "status-tag" not in rows[ul_unknown.infohash]


def test_url_search_no_hidden_urls(dataset, client):
    """URLs that are only linked to items the viewer can't see are not listed"""
    dataset(slug="hidden-url", urls=["https://example.com/hidden"], is_approved=False)

    res = client.get("/urls/search?query=hidden", headers={"HX-Request": "true"})
    assert res.status_code == 200
    assert "example.com/hidden" not in res.text

    res = client.get("/urls/search", headers={"HX-Request": "true"})
    assert "example.com/hidden" not in res.text


def test_url_search_order(dataset, client):
    """
    URLs containing the query as typed come first in lexicographic order,
    then urls that contain each of its terms
    """
    exact = [
        "https://example.com/z",
        "https://example.com/a/very/long/path/that/would/rank/lower",
        "https://example.com/m",
    ]
    loose = "https://other.com/example/com"
    dataset(slug="example", urls=[*exact, loose])

    res = client.get("/urls/search?query=example.com")
    assert res.status_code == 200
    assert [item["url"] for item in res.json()["items"]] == sorted(exact)

    res = client.get("/urls/search", params={"query": "https://example.com/m"})
    assert [item["url"] for item in res.json()["items"]] == ["https://example.com/m"]

    res = client.get("/urls/search", params={"query": "com/a example"})
    assert [item["url"] for item in res.json()["items"]] == [exact[1]]

    res = client.get("/urls/search", params={"query": "example.com/m other"})
    assert [item["url"] for item in res.json()["items"]] == []

    res = client.get("/urls/search", params={"query": "example /com"})
    assert [item["url"] for item in res.json()["items"]] == [loose]


def test_url_search_full_url(dataset, client):
    """A full url can be searched for, and matches the url it was typed from first"""
    url = "https://example.com/some/path?a=1&b=2"
    dataset(slug="example", urls=[url, "https://example.com/other/path"])

    res = client.get("/urls/search", params={"query": url})
    assert res.status_code == 200
    assert [item["url"] for item in res.json()["items"]][0] == url
