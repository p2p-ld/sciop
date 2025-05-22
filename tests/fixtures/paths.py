import logging
from pathlib import Path

import pytest
from _pytest.monkeypatch import MonkeyPatch

TMP_DIR = Path(__file__).parents[1] / "__tmp__"
TORRENT_DIR = TMP_DIR / "torrents"
LOGS_DIR = TMP_DIR / "logs"
DATA_DIR = Path(__file__).parents[1] / "data"


@pytest.fixture
def log_dir(monkeypatch: "MonkeyPatch", tmp_path: Path) -> Path:
    root_logger = logging.getLogger("sciop")
    base_file = tmp_path / "sciop.log"
    root_logger.handlers[0].close()
    monkeypatch.setattr(root_logger.handlers[0], "baseFilename", base_file)
    yield base_file
    root_logger.handlers[0].close()
