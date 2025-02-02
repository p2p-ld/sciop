from sqlmodel import Session, select

from sciop.api.auth import get_password_hash, verify_password
from sciop.models import Account, AccountCreate


def create_account(*, session: Session, account_create: AccountCreate) -> Account:
    db_obj = Account.model_validate(
        account_create, update={"hashed_password": get_password_hash(account_create.password)}
    )
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def get_account(*, session: Session, username: str) -> Account | None:
    statement = select(Account).where(Account.username == username)
    session_user = session.exec(statement).first()
    return session_user


def authenticate(*, session: Session, username: str, password: str) -> Account | None:
    db_user = get_account(session=session, username=username)
    if not db_user:
        return None
    if not verify_password(password, db_user.hashed_password):
        return None
    return db_user
