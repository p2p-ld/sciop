"""whoa meta"""

from sciop.config import config


def test_config_monkeypatch(request):
    assert config.env == "test"
    if request.config.getoption("--persist-db"):
        assert config.db.name == "db.test.sqlite"
    else:
        assert config.db is None
    assert config.secret_key.get_secret_value() == "12345"
