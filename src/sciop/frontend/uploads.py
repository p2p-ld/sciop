from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlmodel import select

from sciop.api.deps import CurrentAccount, RequireUpload, RequireVisibleUpload, SessionDep
from sciop.frontend.templates import jinja, templates
from sciop.models import Upload, UploadRead

uploads_router = APIRouter(prefix="/uploads")


@uploads_router.get("/", response_class=HTMLResponse)
async def uploads(request: Request):
    return templates.TemplateResponse(
        request,
        "pages/uploads.html",
    )


@uploads_router.get("/search")
@jinja.hx("partials/uploads.html")
async def uploads_search(
    query: str = None, session: SessionDep = None, current_account: CurrentAccount = None
) -> Page[UploadRead]:
    if not query or len(query) < 3:
        stmt = (
            select(Upload)
            .where(Upload.visible_to(current_account) == True)
            .order_by(Upload.created_at.desc())
        )
    else:
        stmt = (
            select(Upload)
            .where(Upload.visible_to(current_account) == True)
            .filter(Upload.upload_id.in_(Upload.search_statement(query)))
        )
    return paginate(conn=session, query=stmt)


@uploads_router.get("/{infohash}", response_class=HTMLResponse)
async def upload_show(
    infohash: str,
    account: CurrentAccount,
    session: SessionDep,
    request: Request,
    upload: RequireVisibleUpload,
):
    return templates.TemplateResponse(
        request,
        "pages/upload.html",
        {"upload": upload},
    )


@uploads_router.get("/{infohash}/partial", response_class=HTMLResponse)
async def upload_partial(
    infohash: str,
    request: Request,
    upload: RequireUpload,
):
    return templates.TemplateResponse(request, "partials/upload.html", {"upload": upload})
