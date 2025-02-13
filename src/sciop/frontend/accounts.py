from fastapi import APIRouter
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlmodel import select

from sciop.api.deps import (
    SessionDep,
)
from sciop.frontend.templates import jinja
from sciop.models import Account, AccountRead

accounts_router = APIRouter(prefix="/accounts")


@accounts_router.get("/")
async def accounts():
    raise NotImplementedError()


@accounts_router.post("/{username}")
def account(username: str):
    raise NotImplementedError()


@accounts_router.get("/{username}/partial")
@jinja.hx("partials/account.html")
def account_partial(username: str):
    return None


@accounts_router.get("/search")
@jinja.hx("partials/accounts.html")
async def accounts_search(query: str = None, session: SessionDep = None) -> Page[AccountRead]:
    if not query or len(query) < 3:
        stmt = select(Account).order_by(Account.username)
    else:
        stmt = select(Account).filter(Account.account_id.in_(Account.search_statement(query)))
    return paginate(conn=session, query=stmt)
