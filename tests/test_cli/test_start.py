import shutil
import subprocess
from time import sleep

import pytest
import requests
import yaml
from bs4 import BeautifulSoup


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
        "server": {"port": 8965},
        "instance": {"footer": footer},
    }
    with open(config_path, "w") as f:
        yaml.safe_dump(test_config, f)
    sciop_path = shutil.which("sciop")

    proc = subprocess.Popen(
        " ".join([sciop_path, "start", "-c", str(config_path)]),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=True,
    )
    try:
        # wait until the server is started
        while True:
            stderr = proc.stderr.readline()
            if "startup complete" in stderr:
                break
            sleep(0.1)

        # this tests if the pre-launch stuff works
        res = requests.get("http://localhost:8965/")
        assert res.status_code == 200

        # and this tests if our config has been persisted through
        soup = BeautifulSoup(res.text, "lxml")
        footer_text = soup.select(".footer-id p")
        assert footer_text[0].text == footer

    finally:
        proc.terminate()
