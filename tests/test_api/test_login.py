import pytest
from fastapi.testclient import TestClient

from sciop.config import config


@pytest.mark.parametrize(
    "username", ["name with spaces", "superlongname" * 50, "!!!!!!", "'); DROP ALL TABLES; --", ""]
)
def test_register_bogus_username(username, client: TestClient):
    """
    We reject bogus usernames
    """
    response = client.post(
        config.api_prefix + "/register",
        data={"username": username, "password": "super sick password1"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    assert response.status_code == 422
    # just check that we have some kind of response with an explanation
    assert len(response.json()["detail"][0]["msg"]) > 0
    assert response.json()["detail"][0]["loc"] == ["body", "username"]
