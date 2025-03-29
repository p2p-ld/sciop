from typing import TYPE_CHECKING

import pytest
from faker import Faker

from sciop.services.stats import get_n_files, get_peer_stats

if TYPE_CHECKING:
    from sciop.models import Dataset, TorrentFile


@pytest.fixture
def countables(dataset, upload, torrentfile, uploader) -> list["Dataset"]:
    fake = Faker()
    datasets = []
    for _ in range(3):
        ds: Dataset = dataset(
            slug="-".join(fake.words(3)),
        )
        for _ in range(3):
            tf: TorrentFile = torrentfile(total_size=1000)
            tf.tracker_links[0].seeders = 5
            tf.tracker_links[0].leechers = 10
            upload(dataset_=ds, torrentfile_=tf)
        datasets.append(ds)
    return datasets


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
