from pathlib import Path
from textwrap import dedent

import pytest
import yaml
from click.testing import CliRunner

from sciop.cli.config import config as cli_config
from sciop.cli.config import config_copy, config_set
from sciop.config import Config


@pytest.fixture
def tmp_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("SCIOP_ENV")
    cfg = {"env": "dev", "base_url": "test", "logs": {"level": "ERROR"}}
    with open(tmp_path / "sciop.yaml", "w") as f:
        yaml.safe_dump(cfg, f)


def test_config_show(tmp_config):
    """
    `sciop config` shows the current config and defaults
    :param tmp_config:
    :return:
    """
    runner = CliRunner()
    result = runner.invoke(cli_config)
    assert result.exit_code == 0
    res = result.stdout
    lines = res.splitlines()

    # find defaults line. it being present is enough for now
    defaults_idx = 0
    for i, line in enumerate(lines):
        if "Defaults" in line:
            defaults_idx = i

    assert defaults_idx != 0

    # explicitly set
    assert "sciop.yaml" in res
    assert any(["base_url: test" in line for line in lines[:defaults_idx]])


def test_config_set(tmp_config, tmp_path):
    """
    `sciop config set` can set simple and nested config values
    :param tmp_config:
    :return:
    """
    runner = CliRunner()
    result = runner.invoke(config_set, ["base_url=newtest", "logs.level=INFO"])
    assert result.exit_code == 0
    assert result.stdout == "Updated config:\n{'base_url': 'newtest', 'logs': {'level': 'INFO'}}\n"

    with open(tmp_path / "sciop.yaml") as f:
        cfg = yaml.safe_load(f)

    assert cfg["base_url"] == "newtest"
    assert cfg["logs"]["level"] == "INFO"

    config = Config()
    assert config.base_url == "newtest"
    assert config.logs.level == "INFO"


def test_config_set_roundtrip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """
    Setting a config value from the cli roundtrips any formatting in the file as well
    """
    monkeypatch.chdir(tmp_path)
    cfg = dedent(
        """
    # making a very informative comment
    env: dev
    db: ./test.sqlite
    base_url: test
    
    # logging config
    logs:
      level: DEBUG
    """
    )
    with open(tmp_path / "sciop.yaml", "w") as f:
        f.write(cfg)

    runner = CliRunner()
    result = runner.invoke(config_set, ["base_url=newtest", "logs.level=INFO"])
    assert result.exit_code == 0
    with open(tmp_path / "sciop.yaml") as f:
        cfg = f.read()

    expected = dedent(
        """    # making a very informative comment
    env: dev
    db: ./test.sqlite
    base_url: newtest
    
    # logging config
    logs:
      level: INFO
    """
    )
    assert cfg == expected


def test_config_copy(tmp_path):
    """
    `sciop config copy` makes a new default config
    """
    runner = CliRunner()
    result = runner.invoke(config_copy, ["-o", str(tmp_path / "sciop.yaml")])
    assert result.exit_code == 0
    with open(tmp_path / "sciop.yaml") as f:
        cfg = yaml.safe_load(f)

    # we made a secret key
    assert len(cfg["secret_key"]) == 64
    # default should be valid
    _ = Config(**cfg)
