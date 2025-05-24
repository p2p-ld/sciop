from bs4 import BeautifulSoup as bs


def test_hit_counter(client):
    """
    The hit counter on the main page should! be! a! hit! counter!
    """

    def _get_count(page: str) -> int:
        soup = bs(page, "lxml")
        counter = soup.select_one(".hit-counter")
        return int(counter.text.strip())

    for i in range(5):
        response = client.get("/")
        assert response.status_code == 200
        assert _get_count(response.text) == i
