from typing import Any
from typing import Callable as C

import pytest
from _pytest.monkeypatch import MonkeyPatch

from sciop import get_config


def _set_config(monkeypatch: MonkeyPatch, *args: Any, **kwargs: Any) -> None:
    config = get_config()
    if len(args) == 1 and isinstance(args[0], dict):
        kwargs = args[0]
    for k, v in kwargs.items():
        parts = k.split(".")
        if len(parts) == 1:
            monkeypatch.setattr(config, k, v)
        else:
            set_on = config
            for part in parts[:-1]:
                set_on = getattr(set_on, part)
            monkeypatch.setattr(set_on, parts[-1], v)


@pytest.fixture
def set_config(monkeypatch: MonkeyPatch) -> C:
    """
    Set a value on the config.

    Top-level values can be set like
    set_config(val="something")

    Nested values can be set like
    set_config({"nested.value": "something"})
    """

    def _inner(*args: Any, **kwargs: Any) -> None:
        return _set_config(monkeypatch, *args, **kwargs)

    return _inner


@pytest.fixture(scope="module")
def set_config_module(monkeypatch_module: MonkeyPatch) -> C:
    """
    Set a value on the config.

    Top-level values can be set like
    set_config(val="something")

    Nested values can be set like
    set_config({"nested.value": "something"})
    """

    def _inner(*args: Any, **kwargs: Any) -> None:
        return _set_config(monkeypatch_module, *args, **kwargs)

    return _inner
