from collections.abc import Generator
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from pydantic import ValidationError
from sqlmodel import Session

from sciop.api.auth import ALGORITHM
from sciop.config import config
from sciop.db import get_session
from sciop.models import Account, TokenPayload


reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{config.api_prefix}/login/access-token"
)


SessionDep = Annotated[Session, Depends(get_session)]
TokenDep = Annotated[str, Depends(reusable_oauth2)]


def get_current_account(session: SessionDep, token: TokenDep) -> Account:
    try:
        payload = jwt.decode(
            token, config.secret_key, algorithms=[ALGORITHM]
        )
        token_data = TokenPayload(**payload)
    except (InvalidTokenError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        )
    account = session.get(Account, token_data.sub)
    if not account:
        raise HTTPException(status_code=404, detail="User not found")
    return account


CurrentAccount = Annotated[Account, Depends(get_current_account)]


def get_current_active_admin(current_account: CurrentAccount) -> Account:
    if 'admin' not in current_account.scopes:
        raise HTTPException(
            status_code=403, detail="The user doesn't have enough privileges"
        )
    return current_account