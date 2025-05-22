import os
from pathlib import Path
from time import time

import pytest
import yaml

from sciop.config.main import Config, get_config


def test_config_yaml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """
    We should get config from sciop.yaml if it's present
    """
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("SCIOP_ENV")
    cfg = {"env": "dev", "server": {"base_url": "test"}}
    with open(tmp_path / "sciop.yaml", "w") as f:
        yaml.safe_dump(cfg, f)
    config = Config()
    assert config.env == "dev"
    assert config.server.base_url == "test"


def test_config_env_overrides(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """
    Env vars override yaml values
    """
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("SCIOP_ENV")
    cfg = {"env": "dev", "server": {"base_url": "test"}}
    with open(tmp_path / "sciop.yaml", "w") as f:
        yaml.safe_dump(cfg, f)

    monkeypatch.setenv("SCIOP_SERVER__BASE_URL", "testenv")
    config = Config()
    assert config.env == "dev"
    assert config.server.base_url == "testenv"


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


@pytest.mark.parametrize("default", [True, False])
def test_config_autoload(tmp_path_factory, monkeypatch: pytest.MonkeyPatch, default: bool):
    """
    Config should check for updates in source files after delay
    """
    from sciop.config import main

    tmp_path = tmp_path_factory.mktemp(str(default))

    monkeypatch.chdir(tmp_path)
    if default:
        config_path = tmp_path / "sciop.yaml"
    else:
        config_path = tmp_path / "never-use-this-for-a-config-filename.yaml"
    footer = "you can just put whatever you want here"
    cfg = {"instance": {"footer": footer}}
    with open(config_path, "w") as f:
        yaml.safe_dump(cfg, f)

    # create a version of the config as it would be either if passed with -c
    # or loaded normally from default locations
    new_config = Config() if default else Config.load(config_path)

    monkeypatch.setattr(main, "_config", new_config)
    config_1 = get_config()
    assert config_1.instance.footer == footer
    assert config_1._yaml_source == config_path

    # force checking mtime by pretending we last checked a long time ago
    # without changes, shouldn't reload (object memory id should be unchanged)
    main._config._last_checked = time() - 100000
    assert get_config() is config_1
    assert get_config().instance.footer == footer

    # now update it and force the mtime check again
    new_footer = "and change it whenever you want too"
    cfg = {"instance": {"footer": new_footer}}
    with open(config_path, "w") as f:
        yaml.safe_dump(cfg, f)

    main._config._last_checked = time() - 100000
    assert main._config.should_reload()
    # doing this check updates the check time, so we have to do it twice.
    assert not main._config.should_reload()
    main._config._last_checked = time() - 100000
    config_2 = get_config()
    assert config_2.instance.footer == new_footer
    assert config_1 is not config_2
    assert config_2._yaml_source == config_path
