"""whoa meta"""

from sciop.config import config


def test_config_monkeypatch():
    assert config.env == "test"
    assert config.db.name == "db.test.sqlite"
    assert config.secret_key.get_secret_value() == "12345"
