from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlmodel import select

from sciop.api.deps import (
    CurrentAccount,
    RequireAdmin,
    RequireCurrentAccount,
    RequireReviewer,
    SessionDep,
)
from sciop.frontend.templates import jinja, templates
from sciop.models import Account, AccountRead, AuditLog, AuditLogRead, Dataset, Upload

AuditLogRead.model_rebuild()
self_router = APIRouter(prefix="/self")


@self_router.get("/", response_class=HTMLResponse)
async def profile(request: Request, account: CurrentAccount):
    if account is None:
        return RedirectResponse(url="/login", status_code=302)

    return templates.TemplateResponse(request, "pages/self/index.html")


@self_router.get("/review", response_class=HTMLResponse)
async def review(request: Request, account: RequireReviewer):
    return templates.TemplateResponse(request, "pages/self/review.html")


@self_router.get("/admin", response_class=HTMLResponse)
async def admin(request: Request, account: RequireAdmin):
    return templates.TemplateResponse(request, "pages/self/admin.html")


@self_router.get("/log", response_class=HTMLResponse)
async def log(request: Request, account: RequireReviewer):
    return templates.TemplateResponse(request, "pages/self/log.html")


@self_router.get("/datasets", response_class=HTMLResponse)
async def datasets(request: Request, account: RequireCurrentAccount):
    pass


@self_router.get("/uploads", response_class=HTMLResponse)
async def uploads(request: Request, account: RequireCurrentAccount):
    pass


@self_router.get("/review/datasets", response_class=HTMLResponse)
@jinja.hx("partials/review-datasets.html")
async def review_datasets(account: RequireReviewer, session: SessionDep) -> Page[Dataset]:
    stmt = select(Dataset).where(Dataset.needs_review == True)
    return paginate(conn=session, query=stmt)


@self_router.get("/review/uploads", response_class=HTMLResponse)
@jinja.hx("partials/review-uploads.html")
async def review_uploads(
    request: Request, account: RequireReviewer, session: SessionDep
) -> Page[Upload]:
    stmt = select(Upload).where(Upload.needs_review == True)
    return paginate(conn=session, query=stmt)


@self_router.get("/admin/accounts/search")
@jinja.hx("partials/review-accounts.html")
async def accounts_search(
    query: str = None, session: SessionDep = None, account: RequireAdmin = None
) -> Page[AccountRead]:
    if not query or len(query) < 3:
        stmt = select(Account).order_by(Account.username)
    else:
        stmt = select(Account).filter(Account.account_id.in_(Account.search_statement(query)))
    return paginate(conn=session, query=stmt)


@self_router.get("/log/page")
@jinja.hx("partials/audit-log.html")
async def audit_log(
    account: RequireReviewer,
    session: SessionDep,
) -> Page[AuditLogRead]:

    return paginate(conn=session, query=select(AuditLog).order_by(AuditLog.updated_at.desc()))
