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
        rows = conn.execute(text("SELECT * from webseeds")).fetchall()

    assert len(rows) == 2

    urls = [row[2] for row in rows]
    assert urls == tc.url_list
