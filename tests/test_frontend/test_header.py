from bs4 import BeautifulSoup


def test_header_alert(client, set_config):
    """
    Instance header field should add an alert bar to the header.
    """
    alert = "Some alert text with [markdown](https://example.com)"
    set_config({"instance.alert": alert})
    response = client.get("/")
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "lxml")
    header = soup.select_one(".site-header")
    alert = header.select_one(".alert-content .markdown")
    assert alert.text == "Some alert text with markdown"
    assert alert.select_one("a").attrs["href"] == "https://example.com"
