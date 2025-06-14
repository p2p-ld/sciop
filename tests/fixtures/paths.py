import logging
from pathlib import Path

import pytest
from _pytest.monkeypatch import MonkeyPatch

__all__ = [
    "TMP_DIR",
    "TORRENT_DIR",
    "LOGS_DIR",
    "DATA_DIR",
    "DOCS_DIR",
    "log_dir",
]

TMP_DIR = Path(__file__).parents[1] / "__tmp__"
TORRENT_DIR = TMP_DIR / "torrents"
LOGS_DIR = TMP_DIR / "logs"
DATA_DIR = Path(__file__).parents[1] / "data"
DOCS_DIR = TMP_DIR / "docs"


@pytest.fixture
def log_dir(monkeypatch: "MonkeyPatch", tmp_path: Path) -> Path:
    root_logger = logging.getLogger("sciop")
    base_file = tmp_path / "sciop.log"
    root_logger.handlers[0].close()
    monkeypatch.setattr(root_logger.handlers[0], "baseFilename", base_file)
    yield base_file
    root_logger.handlers[0].close()
