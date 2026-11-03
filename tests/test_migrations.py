"""
These tests are just for our functions that handle migrations,
the actual migrations themselves are tested by pytest-alembic
https://pytest-alembic.readthedocs.io/
and imported here
"""

# ruff: noqa: F401

from datetime import datetime
from pathlib import Path

from pytest_alembic.tests import (
    test_model_definitions_match_ddl,
    test_single_head_revision,
    test_up_down_consistency,
    test_upgrade,
)
from sqlalchemy import text
from torrent_models import Torrent, TorrentCreate

from .fixtures.paths import TORRENT_DIR


def test_6aeff935f1c3_adds_webseeds(alembic_runner, alembic_engine, tmp_path):
    """
    Torrents that have webseeds in them have those webseeds created in the db
    """
    with open(tmp_path / "a", "wb") as f:
        f.write(bytes(16 * (2**10)))

    tc = TorrentCreate(
        path_root=tmp_path,
        piece_length=16 * (2**10),
        trackers=["https://example.com/announce"],
        url_list=["https://example.com/data", "https://other.example.com/data"],
    )
    t = tc.generate(version="v2")
    (TORRENT_DIR / t.v2_infohash).mkdir(exist_ok=True)
    t.write(TORRENT_DIR / t.v2_infohash / "a.torrent")

    alembic_runner.migrate_up_before("6aeff935f1c3")
    alembic_runner.insert_into(
        "torrent_files",
        {
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
            "file_name": "a.torrent",
            "v2_infohash": t.v2_infohash,
            "version": "v2",
            "total_size": t.total_size,
            "piece_size": t.info.piece_length,
            "torrent_size": (Path(TORRENT_DIR) / t.v2_infohash / "a.torrent").stat().st_size,
            "account_id": 0,
            "upload_id": 0,
            "short_hash": t.v2_infohash[0:7],
        },
    )
    alembic_runner.migrate_up_one()
    with alembic_engine.connect() as conn:
        rows = conn.execute(text("SELECT url, is_approved from webseeds")).fetchall()

    assert len(rows) == 2

    urls = [row[0] for row in rows]
    assert set(urls) == set(tc.url_list)
    assert all([row[1] for row in rows])


def test_53e10f088ece_extracts_urls(alembic_runner, alembic_engine):
    """
    Dataset urls are deduplicated into the urls table and linked to their datasets,
    and their edit history is carried over to the link history
    """
    alembic_runner.migrate_up_before("53e10f088ece")
    dataset = {
        "publisher": "pub",
        "source_type": "unknown",
        "source_available": True,
        "source_access": "unknown",
        "scarcity": "unknown",
        "threat": "unknown",
        "scrape_status": "unknown",
        "is_approved": True,
        "is_removed": False,
    }
    alembic_runner.insert_into(
        "datasets",
        [
            {**dataset, "dataset_id": 1, "title": "one", "slug": "one"},
            {**dataset, "dataset_id": 2, "title": "two", "slug": "two"},
        ],
    )
    shared, a, removed = "https://example.com/shared", "https://example.com/a", "https://gone.com/"
    alembic_runner.insert_into(
        "dataset_urls",
        [
            {"dataset_url_id": 1, "dataset_id": 1, "url": shared},
            {"dataset_url_id": 2, "dataset_id": 1, "url": a},
            {"dataset_url_id": 3, "dataset_id": 2, "url": shared},
            {"dataset_url_id": 4, "dataset_id": None, "url": removed},
        ],
    )
    t1, t2 = datetime(2025, 1, 1), datetime(2025, 1, 2)
    alembic_runner.insert_into(
        "dataset_urls__history",
        [
            {"dataset_url_id": 1, "dataset_id": 1, "url": shared, "version_created_at": t1},
            {"dataset_url_id": 2, "dataset_id": 1, "url": a, "version_created_at": t1},
            {"dataset_url_id": 4, "dataset_id": 1, "url": removed, "version_created_at": t1},
            {"dataset_url_id": 1, "dataset_id": 1, "url": shared, "version_created_at": t2},
            {"dataset_url_id": 2, "dataset_id": 1, "url": a, "version_created_at": t2},
            {"dataset_url_id": 4, "dataset_id": None, "url": removed, "version_created_at": t2},
        ],
    )
    alembic_runner.migrate_up_one()

    with alembic_engine.connect() as conn:
        urls = conn.execute(text("SELECT url FROM urls")).fetchall()
        links = conn.execute(text("""
            SELECT l.dataset_id, u.url FROM dataset_url_links l JOIN urls u USING (url_id)
        """)).fetchall()
        history = conn.execute(text("""
            SELECT h.dataset_id, u.url, h.version_is_deletion
            FROM dataset_url_links__history h JOIN urls u USING (url_id)
            ORDER BY h.version_created_at
        """)).fetchall()

    assert sorted(row[0] for row in urls) == sorted([shared, a, removed])
    assert set(links) == {(1, shared), (1, a), (2, shared)}
    assert len(history) == 6
    assert [row for row in history if row[2]] == [(1, removed, 1)]

    alembic_runner.migrate_down_one()
    with alembic_engine.connect() as conn:
        restored = conn.execute(text("SELECT dataset_id, url FROM dataset_urls")).fetchall()
    assert set(restored) == {(1, shared), (1, a), (2, shared)}
