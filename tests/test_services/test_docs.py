import pytest
from bs4 import BeautifulSoup

from sciop.services.docs import build_docs

pytestmark = pytest.mark.docs


def test_docs_debounce(capsys):
    """
    Docs should not build twice if they have been built in the last 10 seconds
    """
    build_docs()
    build_docs()
    captured = capsys.readouterr()
    assert "Not rebuilding" in captured.out


@pytest.mark.parametrize("enabled", [True, False])
def test_show_docs(client, set_config, enabled: bool):
    """
    Display of docs links should be togglable
    """
    set_config({"instance.show_docs": enabled})
    res = client.get("/")
    assert res.status_code == 200
    soup = BeautifulSoup(res.text, "lxml")
    docs_link = soup.select_one('a.nav-link[href="/docs/"]')
    if enabled:
        assert docs_link
    else:
        assert not docs_link
