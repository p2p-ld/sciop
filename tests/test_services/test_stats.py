from typing import TYPE_CHECKING

from bs4 import BeautifulSoup

from sciop.services.stats import get_n_files, get_peer_stats, get_site_stats, update_site_stats

if TYPE_CHECKING:
    from sciop.models import Dataset


def test_peer_stats(countables: list["Dataset"], session):
    counts = get_peer_stats(session)
    # manually count expected values
    n_downloaders = 0
    n_seeders = 0
    total_capacity = 0
    total_size = 0
    for ds in countables:
        for upload in ds.uploads:
            n_downloaders += upload.leechers
            n_seeders += upload.seeders
            total_size += upload.size
            total_capacity += upload.size * upload.seeders
    for k, v in counts.items():
        assert v == locals()[k]


def test_get_n_files(countables: list["Dataset"], session):
    counted_n_files = get_n_files(session)
    # manually count expected values
    n_files = 0
    for ds in countables:
        for upload in ds.uploads:
            n_files += upload.torrent.n_files
    assert counted_n_files == n_files


def test_stats_homepage_nostats(countables, client):
    """
    When stats haven't been counted, we still render the homepage
    """
    response = client.get("/")
    assert response.status_code == 200
    soup = BeautifulSoup(response.text, "lxml")
    assert not soup.select_one(".site-stats")


async def test_stats_homepage(countables, client, session):
    """
    Stats render correctly on the homepage
    """
    await update_site_stats()

    response = client.get("/")

    expected = get_site_stats(session).model_dump()

    soup = BeautifulSoup(response.text, "lxml")
    stats = soup.select_one(".site-stats")
    values = stats.select(".value")
    unpacked = {}
    for v in values:
        unpacked[v.attrs["data-key"]] = v.attrs.get("data-value", v.text)

    for k in ("n_datasets", "n_uploads", "n_seeders", "total_size", "n_files", "total_capacity"):
        assert str(expected[k]) == str(unpacked[k])
