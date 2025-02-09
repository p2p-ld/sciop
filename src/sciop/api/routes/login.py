from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Response

from sciop import crud
from sciop.api.auth import create_access_token
from sciop.api.deps import SessionDep
from sciop.config import config
from sciop.crud import create_account, get_account
from sciop.models import Account, AccountCreate, SuccessResponse, Token

login_router = APIRouter()


@login_router.post("/login")
def login(
    account: Annotated[AccountCreate, Form()], session: SessionDep, response: Response
) -> Token:
    account = crud.authenticate(
        session=session, username=account.username, password=account.password
    )
    if account is None:
        raise HTTPException(status_code=400, detail="Incorrect username or password")

    access_token_expires = timedelta(minutes=config.token_expire_minutes)
    token = create_access_token(account.id, expires_delta=access_token_expires)
    response.set_cookie(key="access_token", value=token, httponly=True)
    response.headers["HX-Location"] = "/self"
    return Token(access_token=token)


@login_router.post("/logout")
def logout(response: Response) -> SuccessResponse:
    response.delete_cookie(key="access_token")
    response.headers["HX-Location"] = "/"
    return SuccessResponse(success=True)


@login_router.post("/register", response_model_exclude={"hashed_password"})
def register(
    account: Annotated[AccountCreate, Form()], session: SessionDep, response: Response
) -> Account:
    existing_account = get_account(session=session, username=account.username)
    if existing_account:
        raise HTTPException(
            status_code=400,
            detail="The user with this username already exists in the system.",
        )
    created_account = create_account(session=session, account_create=account)
    access_token_expires = timedelta(minutes=config.token_expire_minutes)
    token = create_access_token(created_account.id, access_token_expires)
    response.set_cookie(key="access_token", value=token)
    response.headers["HX-Location"] = "/self"
    return created_account
