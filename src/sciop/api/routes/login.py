from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Form, HTTPException
from starlette.requests import Request
from starlette.responses import Response

from sciop import crud
from sciop.api.auth import create_access_token
from sciop.api.deps import SessionDep
from sciop.config import config
from sciop.crud import create_account, get_account
from sciop.middleware import limiter
from sciop.models import Account, AccountCreate, SuccessResponse, Token

login_router = APIRouter()


@login_router.post("/login")
@limiter.limit("2/minute")
def login(
    request: Request,
    account: Annotated[AccountCreate, Form()],
    session: SessionDep,
    response: Response,
) -> Token:
    account = crud.authenticate(
        session=session, username=account.username, password=account.password
    )
    if account is None:
        raise HTTPException(status_code=400, detail="Incorrect username or password")

    access_token_expires = timedelta(minutes=config.token_expire_minutes)
    token = create_access_token(account.account_id, expires_delta=access_token_expires)
    response.set_cookie(
        key="access_token", value=token, httponly=True, secure=True, samesite="strict"
    )
    response.headers["HX-Location"] = "/self"
    return Token(access_token=token)


@login_router.post("/logout")
def logout(response: Response) -> SuccessResponse:
    response.delete_cookie(key="access_token")
    response.headers["HX-Location"] = "/"
    return SuccessResponse(success=True)


@login_router.post("/register", response_model_exclude={"hashed_password"})
@limiter.limit("1/hour")
def register(
    request: Request,
    account: Annotated[AccountCreate, Form()],
    session: SessionDep,
    response: Response,
) -> Account:
    existing_account = get_account(session=session, username=account.username)
    if existing_account:
        raise HTTPException(
            status_code=400,
            detail="The user with this username already exists in the system.",
        )
    created_account = create_account(session=session, account_create=account)
    access_token_expires = timedelta(minutes=config.token_expire_minutes)
    token = create_access_token(created_account.account_id, access_token_expires)
    response.set_cookie(
        key="access_token", value=token, httponly=True, secure=True, samesite="strict"
    )
    response.headers["HX-Location"] = "/self"
    return created_account
