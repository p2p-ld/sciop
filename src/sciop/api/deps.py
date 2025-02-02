from typing import Annotated, Optional

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from pydantic import ValidationError
from sqlmodel import Session

from sciop.api.auth import ALGORITHM
from sciop.config import config
from sciop.db import get_session
from sciop.models import Account, TokenPayload


class OAuth2PasswordBearerCookie(OAuth2PasswordBearer):
    """Password bearer that can also get a jwt from a cookie"""

    def __init__(self, cookie_key="access_token", **kwargs):
        self.cookie_key = cookie_key
        super().__init__(**kwargs)

    async def __call__(self, request: Request) -> Optional[str]:
        authorization = request.cookies.get(self.cookie_key)
        if not authorization:
            return await super().__call__(request)
        else:
            return authorization


reusable_oauth2 = OAuth2PasswordBearerCookie(
    cookie_key="access_token", tokenUrl=f"{config.api_prefix}/login", auto_error=False
)


SessionDep = Annotated[Session, Depends(get_session)]
TokenDep = Annotated[str, Depends(reusable_oauth2)]


def require_current_account(session: SessionDep, token: TokenDep) -> Account:

    try:
        payload = jwt.decode(token, config.secret_key, algorithms=[ALGORITHM])
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


def get_current_account(session: SessionDep, token: TokenDep) -> Optional[Account]:
    try:
        return require_current_account(session, token)
    except HTTPException:
        return None


RequireCurrentAccount = Annotated[Account, Depends(require_current_account)]
CurrentAccount = Annotated[Optional[Account], Depends(get_current_account)]


def get_current_active_admin(current_account: CurrentAccount) -> Account:
    if "admin" not in current_account.scopes:
        raise HTTPException(status_code=403, detail="The user doesn't have enough privileges")
    return current_account
