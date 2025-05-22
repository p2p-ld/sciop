"""whoa meta"""

from sciop.config import get_config


def test_config_monkeypatch(request):
    assert get_config().env == "test"
    if request.config.getoption("--file-db"):
        assert get_config().paths.db.name == "db.test.sqlite"
    else:
        assert get_config().paths.db == "memory"
    assert get_config().secret_key.get_secret_value() == "1" * 64
