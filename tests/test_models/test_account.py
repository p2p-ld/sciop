import pytest
import sqlalchemy
from pydantic import ValidationError
from sqlmodel import select

from sciop.models import Account, AccountCreate, Scopes


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


HAS_SCOPE_CASES = (
    [["root"], False, True, False, False],
    [["admin"], True, True, False, False],
    [["upload"], True, True, True, False],
    [["submit", "review"], True, True, False, True],
)


@pytest.mark.parametrize("scope,admin_has,root_has,uploader_has,submit_has", HAS_SCOPE_CASES)
def test_has_scope(
    scope, admin_has, root_has, uploader_has, submit_has, admin_user, root_user, uploader, account
):
    """
    Has scope returns bool of whether an account has a scope,
    True for all scopes if user is root/admin, except for root, which is only true for roots
    """
    submitter = account(username="submitter", scopes=["submit"])
    assert admin_user.has_scope(*scope) == admin_has
    assert root_user.has_scope(*scope) == root_has
    assert uploader.has_scope(*scope) == uploader_has
    assert submitter.has_scope(*scope) == submit_has


@pytest.mark.parametrize("scope,admin_has,root_has,uploader_has,submit_has", HAS_SCOPE_CASES)
def test_has_scope_expression(
    scope,
    admin_has,
    root_has,
    uploader_has,
    submit_has,
    admin_user,
    root_user,
    uploader,
    account,
    session,
):
    """
    Has scope returns bool of whether an account has a scope,
    True for all scopes if user is root/admin, except for root, which is only true for roots
    """
    submitter = account(username="submitter", scopes=["submit"])
    expected = []
    if admin_has:
        expected.append(admin_user)
    if root_has:
        expected.append(root_user)
    if uploader_has:
        expected.append(uploader)
    if submit_has:
        expected.append(submitter)

    matches = session.exec(select(Account).where(Account.has_scope(*scope))).all()
    assert sorted(matches, key=lambda x: x.username) == sorted(expected, key=lambda x: x.username)


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


def test_username_uniqueness_case_insensitive(account):
    acct1 = account(username="Original", create_only=True)
    with pytest.raises(sqlalchemy.exc.IntegrityError):
        acct2 = account(username="original", create_only=True)
