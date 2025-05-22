import pytest
from fastapi.testclient import TestClient

from sciop.config import get_config


@pytest.mark.parametrize(
    "username", ["name with spaces", "superlongname" * 50, "!!!!!!", "'); DROP ALL TABLES; --", ""]
)
def test_register_bogus_username(username, client: TestClient):
    """
    We reject bogus usernames
    """
    response = client.post(
        get_config().api_prefix + "/register",
        data={"username": username, "password": "super sick password123"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    assert response.status_code == 422
    # just check that we have some kind of response with an explanation
    assert len(response.json()["detail"][0]["msg"]) > 0
    assert response.json()["detail"][0]["loc"] == ["body", "username"]


def test_register_case_insensitive(client: TestClient):
    """
    Don't allow a username to be created twice, case-insensitively
    """
    response = client.post(
        get_config().api_prefix + "/register",
        data={"username": "Original", "password": "super sick password123"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 200

    response2 = client.post(
        get_config().api_prefix + "/register",
        data={"username": "original", "password": "super sick password123"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response2.status_code == 400
    assert "already exists" in response2.json()["detail"]
