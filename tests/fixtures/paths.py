import logging
from pathlib import Path

import pytest
from _pytest.monkeypatch import MonkeyPatch

TMP_DIR = Path(__file__).parents[1] / "__tmp__"
TMP_DIR.mkdir(exist_ok=True)
TORRENT_DIR = TMP_DIR / "torrents"
TORRENT_DIR.mkdir(exist_ok=True)
DATA_DIR = Path(__file__).parents[1] / "data"


@pytest.fixture
def log_dir(monkeypatch: "MonkeyPatch", tmp_path: Path) -> Path:
    root_logger = logging.getLogger("sciop")
    base_file = tmp_path / "sciop.log"
    root_logger.handlers[0].close()
    monkeypatch.setattr(root_logger.handlers[0], "baseFilename", base_file)
    return base_file
