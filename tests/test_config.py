import os
from pathlib import Path

import pytest
import yaml

from sciop.config import Config


def test_config_yaml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """
    We should get config from sciop.yaml if it's present
    """
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("SCIOP_ENV")
    cfg = {"env": "dev", "base_url": "test"}
    with open(tmp_path / "sciop.yaml", "w") as f:
        yaml.safe_dump(cfg, f)
    config = Config()
    assert config.env == "dev"
    assert config.base_url == "test"


def test_config_env_overrides(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """
    Env vars override yaml values
    """
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("SCIOP_ENV")
    cfg = {"env": "dev", "base_url": "test"}
    with open(tmp_path / "sciop.yaml", "w") as f:
        yaml.safe_dump(cfg, f)

    monkeypatch.setenv("SCIOP_BASE_URL", "testenv")
    config = Config()
    assert config.env == "dev"
    assert config.base_url == "testenv"


def test_config_defaults(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """
    Config should be instantiable with default values without having any declared.
    """

    # move to directory without any configs, and clear any env vars
    monkeypatch.chdir(tmp_path)
    for key in os.environ:
        if key.startswith("SCIOP_"):
            monkeypatch.delenv(key)

    _ = Config()
