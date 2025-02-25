from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlmodel import select

from sciop.api.deps import RequireAccount, SessionDep
from sciop.frontend.templates import jinja, templates
from sciop.models import Account, AccountRead, Dataset, Upload

accounts_router = APIRouter(prefix="/accounts")


@accounts_router.get("/{username}", response_class=HTMLResponse)
def account(username: str, account: RequireAccount, request: Request) -> AccountRead:
    return templates.TemplateResponse(request, "pages/account.html", {"account": account})


@accounts_router.get("/{username}/partial")
@jinja.hx("partials/account.html")
def account_partial(username: str):
    return None


@accounts_router.get("/{username}/datasets", response_class=HTMLResponse)
@jinja.hx("partials/datasets.html")
def account_datasets(
    session: SessionDep, request: Request, account: RequireAccount
) -> Page[Dataset]:
    stmt = select(Dataset).where(Dataset.account == account).order_by(Dataset.updated_at.desc())
    return paginate(conn=session, query=stmt)


@accounts_router.get("/{username}/uploads", response_class=HTMLResponse)
@jinja.hx("partials/uploads.html")
def account_uploads(session: SessionDep, request: Request, account: RequireAccount) -> Page[Upload]:
    stmt = select(Upload).where(Upload.account == account).order_by(Upload.updated_at.desc())
    return paginate(conn=session, query=stmt)


@accounts_router.get("/search")
@jinja.hx("partials/accounts.html")
async def accounts_search(query: str = None, session: SessionDep = None) -> Page[AccountRead]:
    if not query or len(query) < 3:
        stmt = select(Account).order_by(Account.username)
    else:
        stmt = select(Account).filter(Account.account_id.in_(Account.search_statement(query)))
    return paginate(conn=session, query=stmt)
