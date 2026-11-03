import shutil
import subprocess
from time import sleep

import httpx
import pytest
import yaml
from bs4 import BeautifulSoup


@pytest.mark.docs
@pytest.mark.slow
@pytest.mark.timeout(30)
def test_start_with_config(tmp_path, monkeypatch):
    """
    When passing a config with -c, we should actually use it in the app!
    """
    monkeypatch.chdir(tmp_path)
    config_path = tmp_path / "sciop-test-fakename.yaml"
    footer = "this text should be in the footer!"
    test_config = {
        "env": "test",
        "server": {"port": 8965},
        "instance": {"footer": footer},
        "services": {"docs": {"enabled": False}},
    }
    with open(config_path, "w") as f:
        yaml.safe_dump(test_config, f)
    sciop_path = shutil.which("sciop")

    proc = subprocess.Popen(
        [sciop_path, "start", "-c", str(config_path)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    output = []
    try:
        # wait until the server is started
        for line in proc.stdout:
            output.append(line)
            if "startup complete" in line:
                break
        else:
            pytest.fail("sciop exited before starting")
        sleep(0.25)

        # this tests if the pre-launch configuration stuff works
        res = httpx.get("http://localhost:8965/")
        assert res.status_code == 200

        # and this tests if our config has been persisted through
        soup = BeautifulSoup(res.text, "lxml")
        footer_text = soup.select(".footer-id p")
        assert footer_text[0].text == footer

    finally:
        # pytest shows this if the test fails, including from pytest-timeout
        print("".join(output))
        proc.terminate()
        proc.wait(timeout=10)
