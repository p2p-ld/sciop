from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, Response
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlmodel import select

from sciop.api.deps import (
    CurrentAccount,
    RequireEditableBy,
    RequireUpload,
    RequireVisibleUpload,
    SearchQuery,
    SessionDep,
)
from sciop.frontend.templates import jinja, templates
from sciop.models import SearchPage, Upload, UploadRead, UploadUpdate

uploads_router = APIRouter(prefix="/uploads")


@uploads_router.get("/", response_class=HTMLResponse)
async def uploads(request: Request, search: SearchQuery):
    query_str = search.to_query_str()
    return templates.TemplateResponse(request, "pages/uploads.html", {"query_str": query_str})


@uploads_router.get("/search")
@jinja.hx("partials/uploads.html")
async def uploads_search(
    search: SearchQuery, session: SessionDep, current_account: CurrentAccount, response: Response
) -> SearchPage[UploadRead]:
    if not search.query or len(search.query) < 3:
        stmt = (
            select(Upload)
            .join(Upload.torrent)
            .where(Upload.visible_to(current_account) == True)
            .order_by(Upload.created_at.desc())
        )
    else:
        stmt = (
            Upload.search(search.query)
            .join(Upload.torrent)
            .where(Upload.visible_to(current_account) == True)
        )

    stmt = search.apply_sort(stmt, model=Upload)
    if search.should_redirect():
        response.headers["HX-Replace-Url"] = f"{search.to_query_str()}"
    else:
        response.headers["HX-Replace-Url"] = "/datasets/"

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


@uploads_router.get("/{infohash}/edit", response_class=HTMLResponse)
async def upload_edit(
    infohash: str,
    upload: RequireVisibleUpload,
    current_account: RequireEditableBy,
    request: Request,
):
    upload_update = UploadUpdate.from_upload(upload)
    return templates.TemplateResponse(
        request,
        "pages/upload-edit.html",
        {
            "upload": upload_update,
            "dataset": upload.dataset,
            "parts": upload.dataset.parts,
            "torrent": upload.torrent,
        },
    )


@uploads_router.get("/{infohash}/partial", response_class=HTMLResponse)
async def upload_partial(
    infohash: str,
    request: Request,
    upload: RequireUpload,
):
    return templates.TemplateResponse(request, "partials/upload.html", {"upload": upload})
