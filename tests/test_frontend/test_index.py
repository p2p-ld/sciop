import bs4
from bs4 import BeautifulSoup as bs
from faker import Faker

from sciop.config import InstanceQuote


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


def test_random_quotes(client, set_config):
    """
    We should be able to cycle through random quotes on the main page!
    """
    fake = Faker()

    quotes = [
        InstanceQuote(
            content=fake.text(),
            attribution=fake.name(),
            link_text=" ".join(fake.words()),
            link=fake.url(),
        )
        for _ in range(50)
    ]
    set_config({"instance.quotes": quotes})

    quote_texts = [q.content for q in quotes]

    def _get_quote_text(page: str) -> str:
        soup = bs(page, "lxml")
        quote = soup.select_one("blockquote")
        assert quote is not None, "Quote not found on page!"
        # get just the text of the quote, not the inner contents of attribution
        quote_text = "".join(
            [str(t) for t in quote.contents if type(t) is bs4.element.NavigableString]
        )
        return quote_text.strip().lstrip('"').rstrip('"')

    # odds we don't see two of our 50 quotes in 5 page loads is (1/50)^5
    # so we will get a false negative here once every 312 million runs
    seen = set()
    for _ in range(5):
        res = client.get("/")
        assert res.status_code == 200
        quote = _get_quote_text(res.text)
        assert quote in quote_texts
        seen.add(quote)

    assert len(seen) > 1
