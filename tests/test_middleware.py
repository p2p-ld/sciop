import logging

import pytest

from sciop.config import config
from sciop.logging import init_logger


@pytest.mark.parametrize("level", (logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR))
@pytest.mark.parametrize("status_code", (200, 404, 500))
def test_logging(
    client, monkeypatch, capsys, tmp_path, log_dir, log_console_width, level, status_code
):
    monkeypatch.setattr(config.logs, "level_file", level)
    monkeypatch.setattr(config.logs, "level_stdout", level)
    monkeypatch.setattr(config.logs, "dir", tmp_path)

    # clear the root logger so it gets recreated
    # but monkeypatch so we don't mess up other tests
    root_logger = logging.getLogger("sciop")
    logger = logging.getLogger("sciop.requests")
    monkeypatch.setattr(root_logger, "handlers", [])
    monkeypatch.setattr(root_logger, "level", level)
    monkeypatch.setattr(logger, "level", level)

    init_logger("sciop.requests", level=level, log_dir=tmp_path)
    init_logger("sciop", level=level, log_dir=tmp_path)

    expected = None
    if status_code == 200:
        response = client.get("/")
        if level in (logging.DEBUG, logging.INFO):
            expected = "[200] GET: /"
    elif status_code == 404:
        response = client.get("/somefakeurlthatshouldneverexist")
        if level in (logging.DEBUG, logging.INFO):
            expected = "[404] GET: /somefakeurlthatshouldneverexist"
    elif status_code == 500:
        response = client.post("/test/500")
        # 500s are internal server errors so we should log them like errors yno
        expected = '[500] POST: /test/500 - {"detail":'
    else:
        raise ValueError()

    stdout = capsys.readouterr().out.split("\n")
    with open(log_dir) as f:
        log_entries = f.readlines()

    if expected:
        # logged to stdout and file
        assert expected in stdout[0]
        assert expected in log_entries[-1]
    else:
        assert len(stdout) == 1
        assert stdout[0] == ""
        assert len(log_entries) == 0


def test_security_headers(client):
    response = client.get("/")
    expected_headers = (
        "Content-Security-Policy",
        "Cross-Origin-Opener-Policy",
        "Referrer-Policy",
        "X-Content-Type-Options",
        "X-Frame-Options",
    )

    assert all(header in response.headers for header in expected_headers)
