import pytest
from pydantic import ValidationError

from sciop.models import AccountCreate, Scopes


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


@pytest.mark.parametrize("scope", ["root", "admin", Scopes.root, Scopes.admin])
def test_has_scope_protected_scopes(scope, admin_user):
    """
    Protected scopes root and admin can only ever be used by themselves in a scope check
    """
    with pytest.raises(ValueError, match="can only be used by themselves"):
        _ = admin_user.has_scope(scope, "upload")


@pytest.mark.parametrize("scope", ["review", Scopes.review])
def test_has_scope_from_enum(admin_user, scope):
    """Scope checks should accept strings and enum values"""
    assert admin_user.has_scope(scope)
    assert admin_user.has_scope(scope, Scopes.upload)
    assert admin_user.has_scope(scope, "upload")
