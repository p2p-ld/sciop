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
    then looser matches
    """
    exact = [
        "https://example.com/z",
        "https://example.com/a/very/long/path/that/would/rank/lower",
        "https://example.com/m",
    ]
    loose = "https://other.com/berger-com"
    dataset(slug="berger", urls=[*exact, loose])

    res = client.get("/urls/search?query=example.com")
    assert res.status_code == 200
    assert [item["url"] for item in res.json()["items"]] == [*sorted(exact), loose]
