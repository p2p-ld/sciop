import logging

import pytest
from _pytest.monkeypatch import MonkeyPatch


@pytest.fixture
def log_console_width(monkeypatch: "MonkeyPatch") -> None:
    """
    Set rich console width to be very wide so that log messages print on one line
    """
    root_logger = logging.getLogger("sciop")
    monkeypatch.setattr(root_logger.handlers[1].console, "width", 1000)
