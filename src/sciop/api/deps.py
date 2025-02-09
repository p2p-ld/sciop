from typing import Annotated, Any, Optional, TypeVar

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from pydantic import BaseModel, ValidationError
from sqlmodel import Session

from sciop import crud
from sciop.api.auth import ALGORITHM
from sciop.config import config
from sciop.db import get_session
from sciop.models import Account, Dataset, DatasetInstance, Scopes, TokenPayload

_TModel = TypeVar("_TModel", bound=BaseModel)


class OAuth2PasswordBearerCookie(OAuth2PasswordBearer):
    """Password bearer that can also get a jwt from a cookie"""

    def __init__(self, cookie_key: str = "access_token", **kwargs: Any):
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
    except (InvalidTokenError, ValidationError) as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        ) from e
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


def require_current_active_admin(current_account: RequireCurrentAccount) -> Account:
    if not current_account.has_scope("admin"):
        raise HTTPException(status_code=403, detail="Account must be admin")
    return current_account


def require_current_active_reviewer(current_account: RequireCurrentAccount) -> Account:
    if not current_account.has_scope("review", "admin"):
        raise HTTPException(status_code=403, detail="Account must be reviewer")
    return current_account


def require_current_active_uploader(current_account: RequireCurrentAccount) -> Account:
    if not current_account.has_scope("upload", "admin"):
        raise HTTPException(status_code=403, detail="Account must be reviewer")
    return current_account


RequireAdmin = Annotated[Account, Depends(require_current_active_admin)]
RequireReviewer = Annotated[Account, Depends(require_current_active_reviewer)]
RequireUploader = Annotated[Account, Depends(require_current_active_uploader)]


def require_dataset(dataset_slug: str, session: SessionDep) -> Dataset:
    dataset = crud.get_dataset(session=session, dataset_slug=dataset_slug)
    if not dataset:
        raise HTTPException(
            status_code=404,
            detail=f"No such dataset {dataset_slug} exists!",
        )
    return dataset


def require_enabled_dataset(dataset_slug: str, session: SessionDep) -> Dataset:
    """
    Require that a dataset exists and is enabled
    """
    dataset = require_dataset(dataset_slug, session)
    if not dataset.enabled:
        raise HTTPException(
            status_code=401,
            detail=f"Dataset {dataset_slug} not enabled for uploads",
        )
    return dataset


RequireDataset = Annotated[Dataset, Depends(require_dataset)]
RequireEnabledDataset = Annotated[Dataset, Depends(require_enabled_dataset)]


def require_upload(short_hash: str, session: SessionDep) -> DatasetInstance:
    upload = crud.get_instance_from_short_hash(session=session, short_hash=short_hash)
    if not upload:
        raise HTTPException(
            status_code=404,
            detail=f"No such upload {short_hash} exists!",
        )
    return upload


def require_enabled_upload(short_hash: str, session: SessionDep) -> DatasetInstance:
    upload = require_upload(short_hash, session)
    if not upload.enabled:
        raise HTTPException(
            status_code=401,
            detail=f"Upload {short_hash} is not enabled",
        )
    return upload


RequireUpload = Annotated[DatasetInstance, Depends(require_upload)]
RequireEnabledUpload = Annotated[DatasetInstance, Depends(require_enabled_upload)]


def require_account(username: str, session: SessionDep) -> Account:
    account = crud.get_account(session=session, username=username)
    if not username:
        raise HTTPException(
            status_code=404,
            detail=f"No such account {username} exists!",
        )
    return account


RequireAccount = Annotated[Account, Depends(require_account)]


def valid_scope(scope: str | Scopes) -> Scopes:
    try:
        scope = getattr(Scopes, scope)
    except AttributeError:
        raise HTTPException(
            status_code=404,
            detail=f"No such scope as {scope} exists!",
        ) from None
    return scope


ValidScope = Annotated[Scopes, Depends(valid_scope)]
