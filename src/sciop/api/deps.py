from typing import Annotated, Any, Optional, TypeVar

import jwt
from fastapi import Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from pydantic import BaseModel, ValidationError
from sqlmodel import Session

from sciop import crud
from sciop.api.auth import ALGORITHM
from sciop.config import config
from sciop.db import get_session
from sciop.models import Account, Dataset, DatasetPart, Scopes, Tag, TokenPayload, Upload

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
        payload = jwt.decode(token, config.secret_key.get_secret_value(), algorithms=[ALGORITHM])
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


def require_current_active_root(current_account: RequireCurrentAccount) -> Account:
    if not current_account.has_scope("root"):
        raise HTTPException(status_code=403, detail="Account must be root")
    return current_account


def require_current_active_admin(current_account: RequireCurrentAccount) -> Account:
    if not current_account.has_scope("admin"):
        raise HTTPException(status_code=403, detail="Account must be admin")
    return current_account


def require_current_active_reviewer(current_account: RequireCurrentAccount) -> Account:
    if not current_account.has_scope("review"):
        raise HTTPException(status_code=403, detail="Account must be reviewer")
    return current_account


def require_current_active_uploader(current_account: RequireCurrentAccount) -> Account:
    if not current_account.has_scope("upload"):
        raise HTTPException(status_code=403, detail="Account must be reviewer")
    return current_account


RequireRoot = Annotated[Account, Depends(require_current_active_root)]
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


def require_dataset_part(
    dataset_slug: str, dataset_part_slug: str, session: SessionDep
) -> DatasetPart:
    part = crud.get_dataset_part(
        session=session, dataset_slug=dataset_slug, dataset_part_slug=dataset_part_slug
    )
    if not part:
        raise HTTPException(
            status_code=404,
            detail=f"No such dataset part {dataset_slug}/{dataset_part_slug} exists!",
        )
    return part


RequireDatasetPart = Annotated[DatasetPart, Depends(require_dataset_part)]


def require_upload(infohash: str, session: SessionDep) -> Upload:
    upload = crud.get_upload_from_infohash(session=session, infohash=infohash)
    if not upload:
        raise HTTPException(
            status_code=404,
            detail=f"No such upload {infohash} exists!",
        )
    return upload


def require_enabled_upload(infohash: str, session: SessionDep) -> Upload:
    upload = require_upload(infohash, session)
    if not upload.enabled:
        raise HTTPException(
            status_code=401,
            detail=f"Upload {infohash} is not enabled",
        )
    return upload


RequireUpload = Annotated[Upload, Depends(require_upload)]
RequireEnabledUpload = Annotated[Upload, Depends(require_enabled_upload)]


def require_account(username: str, session: SessionDep) -> Account:
    account = crud.get_account(session=session, username=username)
    if not account:
        raise HTTPException(
            status_code=404,
            detail=f"No such account {username} exists!",
        )
    return account


RequireAccount = Annotated[Account, Depends(require_account)]


def require_tag(tag: str, session: SessionDep) -> Tag:
    existing_tag = crud.get_tag(session=session, tag=tag)
    if not tag:
        raise HTTPException(
            status_code=404,
            detail=f"No such tag {tag} exists!",
        )
    return existing_tag


RequireTag = Annotated[Tag, Depends(require_tag)]


def valid_scope(scope_name: str | Scopes) -> Scopes:
    try:
        scope = getattr(Scopes, scope_name)
    except AttributeError:
        raise HTTPException(
            status_code=404,
            detail=f"No such scope as {scope_name} exists!",
        ) from None
    return scope


ValidScope = Annotated[Scopes, Depends(valid_scope)]


def add_htmx_response_trigger(request: Request, response: Response) -> Response:
    """
    Add an htmx trigger to allow htmx elements to listen to a generic "response" event
    from other elements.

    e.g.:

        <div
          hx-get="/some/thing"
          hx-trigger="response from:.child"
        >
          <div>
            <span
              hx-get="/a/button/maybe"
              class=.child
            >
              assume this does something
            </span>
          </div>
        </div>
    """
    # yield response

    if "hx-request" in request.headers:
        if "hx-trigger" in response.headers:
            response.headers["hx-trigger"] = ",".join([response.headers["hx-trigger"], "response"])
        else:
            response.headers["hx-trigger"] = "response"
    return response


HTMXResponse = Annotated[Response, Depends(add_htmx_response_trigger)]
