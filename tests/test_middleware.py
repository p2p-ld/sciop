import logging

from fastapi.testclient import TestClient

from sciop.config import config
from sciop.main import app

client = TestClient(app)


def test_logging(monkeypatch, capsys, tmp_path, log_dir, log_console_width):
    monkeypatch.setattr(config.logs, "level_file", logging.DEBUG)
    monkeypatch.setattr(config.logs, "level_stdout", logging.DEBUG)
    monkeypatch.setattr(config.logs, "dir", tmp_path)

    logger = logging.getLogger("sciop.requests")
    root_logger = logging.getLogger("sciop")

    expected_lines = ["[200] GET: /", "[404] GET: /somefakeurlthatshouldneverexist"]

    response_200 = client.get("/")
    response_404 = client.get("/somefakeurlthatshouldneverexist")

    # both logged to stdout
    stdout = capsys.readouterr().out.split("\n")
    assert expected_lines[0] in stdout[0]
    assert expected_lines[1] in stdout[1]

    # and to file - root logger should hold the file handler
    with open(log_dir) as f:
        log_entries = f.readlines()

    assert expected_lines[0] in log_entries[0]
    assert expected_lines[1] in log_entries[1]


def test_security_headers():
    response = client.get("/")
    expected_headers = (
        "Content-Security-Policy",
        "Cross-Origin-Opener-Policy",
        "Referrer-Policy",
        "X-Content-Type-Options",
        "X-Frame-Options",
    )

    assert all(header in response.headers for header in expected_headers)
