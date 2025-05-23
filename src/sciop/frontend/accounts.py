from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlmodel import select

from sciop.api.deps import CurrentAccount, RequireAccount, SearchQueryNoCurrentUrl, SessionDep
from sciop.frontend.templates import jinja, templates
from sciop.models import Account, AccountRead, Dataset, DatasetRead, Upload, UploadRead

accounts_router = APIRouter(prefix="/accounts")


@accounts_router.get("/{username}", response_class=HTMLResponse)
def account(username: str, account: RequireAccount, request: Request) -> AccountRead:
    return templates.TemplateResponse(request, "pages/account.html", {"account": account})


@accounts_router.get("/{username}/partial")
@jinja.hx("partials/account.html")
def account_partial(username: str):
    return None


@accounts_router.get("/{username}/datasets")
@jinja.hx("partials/datasets.html")
def account_datasets(
    username: str,
    search: SearchQueryNoCurrentUrl,
    session: SessionDep,
    request: Request,
    account: RequireAccount,
    current_account: CurrentAccount,
) -> Page[DatasetRead]:
    stmt = (
        select(Dataset)
        .where(Dataset.account == account, Dataset.visible_to(current_account) == True)
        .order_by(Dataset.updated_at.desc())
    )
    stmt = search.apply_sort(stmt, Dataset)
    return paginate(conn=session, query=stmt)


@accounts_router.get("/{username}/uploads")
@jinja.hx("partials/uploads.html")
def account_uploads(
    username: str,
    search: SearchQueryNoCurrentUrl,
    session: SessionDep,
    request: Request,
    account: RequireAccount,
    current_account: CurrentAccount,
) -> Page[UploadRead]:
    stmt = (
        select(Upload)
        .where(Upload.account == account, Upload.visible_to(current_account) == True)
        .order_by(Upload.updated_at.desc())
    )
    stmt = search.apply_sort(stmt, Upload)
    return paginate(conn=session, query=stmt)


@accounts_router.get("/search")
@jinja.hx("partials/accounts.html")
async def accounts_search(query: str = None, session: SessionDep = None) -> Page[AccountRead]:
    if not query or len(query) < 3:
        stmt = select(Account).filter(Account.is_suspended == False).order_by(Account.username)
    else:
        stmt = Account.search(query).filter(Account.is_suspended == False)
    return paginate(conn=session, query=stmt)
