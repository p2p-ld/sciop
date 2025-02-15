import pytest
from pydantic import ValidationError

from sciop.models import AccountCreate


@pytest.mark.parametrize(
    "password,valid",
    [
        ("tooshort", False),
        ("nonumbersinthispassword", False),
        ("123456789123456", False),
        ("normalpassword12", True),
    ],
)
def test_password_requirements(password, valid):
    if not valid:
        with pytest.raises(ValidationError):
            _ = AccountCreate(username="whatever", password=password)
    else:
        _ = AccountCreate(username="whatever", password=password)
