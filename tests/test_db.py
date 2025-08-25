import pytest
from sqlalchemy.exc import InvalidRequestError
from sqlmodel import Session, select

from sciop.db import ensure_root
from sciop.models import Account


def test_ensure_root(set_config, session: Session):
    """
    When configured, ensure_root creates a root account if it doesn't exist
    """
    user = "newroot"
    password = "rootpassword12345"
    set_config(root_user=user, root_password=password)

    ensure_root(session)

    acct = session.exec(select(Account).where(Account.username == user)).first()
    assert acct
    updated_at = acct.updated_at

    # running again doesn't try and create the same account and doesn't touch it
    ensure_root(session)
    acct2 = session.exec(select(Account).where(Account.username == user)).first()
    assert acct2.updated_at == updated_at


def test_ensure_root_without_root_configured(set_config, session):
    """
    When no root user is configured, ensure_root doesn't crash and just returns early.
    """
    set_config(root_user=None, root_password=None)
    assert ensure_root(session) is None


def test_get_session_contextmanager(session):
    """
    The get_session function should behave as a context manager
    """
    from sciop.db import get_session

    with get_session() as session:
        # do nothing, we care about the closure
        assert session.is_active

    # trying to use it again should throw an error
    with pytest.raises(InvalidRequestError):
        session.exec(select(Account)).first()
