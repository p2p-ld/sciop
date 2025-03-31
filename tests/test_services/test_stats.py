from typing import TYPE_CHECKING

from sciop.services.stats import get_n_files, get_peer_stats

if TYPE_CHECKING:
    from sciop.models import Dataset


def test_peer_stats(countables: list[Dataset], session):
    counts = get_peer_stats(session)
    # manually count expected values
    n_leechers = 0
    n_seeders = 0
    total_capacity = 0
    total_size = 0
    for ds in countables:
        for upload in ds.uploads:
            n_leechers += upload.leechers
            n_seeders += upload.seeders
            total_size += upload.size
            total_capacity += upload.size * upload.seeders
    for k in ("n_downloaders", "n_seeders", "total_capacity", "total_size"):
        assert counts[k] == locals()[k]


def test_get_n_files(countables: list[Dataset], session):
    counted_n_files = get_n_files(session)
    # manually count expected values
    n_files = 0
    for ds in countables:
        for upload in ds.uploads:
            n_files += upload.torrent.n_files
    assert counted_n_files == n_files
