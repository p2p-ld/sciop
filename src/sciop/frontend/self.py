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
    SearchQueryNoCurrentUrl,
    SessionDep,
)
from sciop.frontend.templates import jinja, templates
from sciop.models import (
    Account,
    AccountRead,
    AuditLog,
    AuditLogRead,
    Dataset,
    DatasetPart,
    DatasetRead,
    Report,
    ReportRead,
    SearchPage,
    Upload,
    UploadRead,
    Webseed,
)

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


@self_router.get("/reports", response_class=HTMLResponse)
async def reports(request: Request, account: RequireReviewer):
    return templates.TemplateResponse(request, "pages/self/reports.html")


@self_router.get("/admin", response_class=HTMLResponse)
async def admin(request: Request, account: RequireAdmin):
    return templates.TemplateResponse(request, "pages/self/admin.html")


@self_router.get("/log", response_class=HTMLResponse)
async def log(request: Request, account: RequireReviewer):
    return templates.TemplateResponse(request, "pages/self/log.html")


@self_router.get("/datasets")
@jinja.hx("partials/datasets.html")
async def datasets(
    search: SearchQueryNoCurrentUrl,
    request: Request,
    account: RequireCurrentAccount,
    session: SessionDep,
) -> SearchPage[DatasetRead]:
    stmt = (
        select(Dataset)
        .where(Dataset.visible_to(account) == True, Dataset.account == account)
        .order_by(Dataset.created_at.desc())
    )
    stmt = search.apply_sort(stmt, Dataset)
    return paginate(conn=session, query=stmt)


@self_router.get("/uploads")
@jinja.hx("partials/uploads.html")
async def uploads(
    search: SearchQueryNoCurrentUrl,
    request: Request,
    account: RequireCurrentAccount,
    session: SessionDep,
) -> SearchPage[UploadRead]:
    stmt = (
        select(Upload)
        .join(Upload.torrent)
        .where(Upload.visible_to(account) == True, Upload.account == account)
        .order_by(Upload.created_at.desc())
    )
    stmt = search.apply_sort(stmt, Upload)
    return paginate(conn=session, query=stmt)


# TODO: Fix awkward url structure here and put all the moderation pages in their own namespace
@self_router.get("/reports-partial")
@jinja.hx("partials/reports.html")
async def reports_partial(
    search: SearchQueryNoCurrentUrl,
    request: Request,
    account: RequireCurrentAccount,
    session: SessionDep,
) -> SearchPage[ReportRead]:
    """Reports opened by the current account"""
    stmt = select(Report).where(Report.opened_by == account).order_by(Report.created_at.desc())
    stmt = search.apply_sort(stmt, Upload)
    return paginate(conn=session, query=stmt)


@self_router.get("/review/datasets")
@jinja.hx("partials/review-datasets.html")
async def review_datasets(
    search: SearchQueryNoCurrentUrl, account: RequireReviewer, session: SessionDep
) -> Page[Dataset]:
    stmt = select(Dataset).where(Dataset.needs_review == True)
    stmt = search.apply_sort(stmt, Dataset)
    return paginate(conn=session, query=stmt)


@self_router.get("/review/dataset-parts")
@jinja.hx("partials/review-parts.html")
async def review_parts(account: RequireReviewer, session: SessionDep) -> Page[DatasetPart]:
    stmt = select(DatasetPart).where(DatasetPart.needs_review == True)
    return paginate(conn=session, query=stmt)


@self_router.get("/review/uploads")
@jinja.hx("partials/review-uploads.html")
async def review_uploads(
    search: SearchQueryNoCurrentUrl, request: Request, account: RequireReviewer, session: SessionDep
) -> Page[Upload]:
    stmt = select(Upload).join(Upload.torrent).where(Upload.needs_review == True)
    stmt = search.apply_sort(stmt, Upload)
    return paginate(conn=session, query=stmt)


@self_router.get("/review/webseeds")
@jinja.hx("partials/review-webseeds.html")
async def review_webseeds(
    request: Request, account: RequireReviewer, session: SessionDep
) -> Page[Webseed]:
    stmt = select(Webseed).where(Webseed.needs_review == True).order_by(Webseed.created_at.desc())
    return paginate(conn=session, query=stmt)


@self_router.get("/admin/accounts/search")
@jinja.hx("partials/review-accounts.html")
async def accounts_search(
    query: str = None, session: SessionDep = None, account: RequireAdmin = None
) -> Page[AccountRead]:
    if not query or len(query) < 3:
        stmt = select(Account).order_by(Account.username)
    else:
        stmt = Account.search(query)
    return paginate(conn=session, query=stmt)


@self_router.get("/log/page")
@jinja.hx("partials/audit-log.html")
async def audit_log(
    account: RequireReviewer,
    session: SessionDep,
) -> Page[AuditLogRead]:

    return paginate(conn=session, query=select(AuditLog).order_by(AuditLog.updated_at.desc()))
