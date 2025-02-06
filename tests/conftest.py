from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from _pytest.monkeypatch import Monkeypatch

TMP_DIR = Path(__file__).parent / "__tmp__"
TMP_DIR.mkdir(exist_ok=True)


@pytest.fixture(autouse=True)
def monkeypatch_config(monkeypatch: "Monkeypatch", tmp_path: Path) -> None:
    from sciop import config

    # do this once we write a way to figure out where the hell the db went
    # db_path = tmp_path / 'db.test.sqlite'

    db_path = TMP_DIR / "db.test.sqlite"
    db_path.unlink(missing_ok=True)

    new_config = config.Config(env="test", db=db_path, secret_key="12345")
    monkeypatch.setattr(config, "config", new_config)
