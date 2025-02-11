from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlmodel import select

from sciop import crud
from sciop.api.deps import (
    CurrentAccount,
    RequireUpload,
    SessionDep,
)
from sciop.config import config
from sciop.frontend.templates import jinja, templates
from sciop.models import Dataset, DatasetRead

uploads_router = APIRouter(prefix="/uploads")


@uploads_router.get("/", response_class=HTMLResponse)
async def uploads(request: Request, account: CurrentAccount, session: SessionDep):
    uploads = crud.get_approved_uploads(session=session)
    return templates.TemplateResponse(
        "pages/uploads.html",
        {"request": request, "config": config, "current_account": account, "uploads": uploads},
    )


@uploads_router.get("/search")
@jinja.hx("partials/uploads.html")
async def uploads_search(query: str = None, session: SessionDep = None) -> Page[DatasetRead]:
    if not query or len(query) < 3:
        stmt = select(Dataset).where(Dataset.enabled == True).order_by(Dataset.created_at)
    else:
        stmt = (
            select(Dataset)
            .where(Dataset.enabled == True)
            .filter(Dataset.id.in_(Dataset.search_statement(query)))
        )
    return paginate(conn=session, query=stmt)


@uploads_router.get("/{short_hash}", response_class=HTMLResponse)
async def upload_show(
    short_hash: str, account: CurrentAccount, session: SessionDep, request: Request
):
    upload = crud.get_upload_from_short_hash(session=session, short_hash=short_hash)
    if not upload:
        raise HTTPException(
            status_code=404,
            detail=f"No such upload {short_hash} exists",
        )
    return templates.TemplateResponse(
        "pages/upload.html",
        {"request": request, "config": config, "current_account": account, "upload": upload},
    )


@uploads_router.get("/{short_hash}/partial", response_class=HTMLResponse)
async def upload_partial(request: Request, upload: RequireUpload):
    return templates.TemplateResponse(
        "partials/upload.html", {"upload": upload, "request": request}
    )
