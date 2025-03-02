from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlmodel import select

from sciop import crud
from sciop.api.deps import CurrentAccount, RequireUpload, RequireVisibleUpload, SessionDep
from sciop.frontend.templates import jinja, templates
from sciop.models import Dataset, DatasetRead

uploads_router = APIRouter(prefix="/uploads")


@uploads_router.get("/", response_class=HTMLResponse)
async def uploads(request: Request, session: SessionDep):
    uploads = crud.get_visible_uploads(session=session)
    return templates.TemplateResponse(
        request,
        "pages/uploads.html",
        {"uploads": uploads},
    )


@uploads_router.get("/search")
@jinja.hx("partials/uploads.html")
async def uploads_search(query: str = None, session: SessionDep = None) -> Page[DatasetRead]:
    if not query or len(query) < 3:
        stmt = select(Dataset).where(Dataset.is_visible == True).order_by(Dataset.created_at)
    else:
        stmt = (
            select(Dataset)
            .where(Dataset.is_visible == True)
            .filter(Dataset.dataset_id.in_(Dataset.search_statement(query)))
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
async def upload_partial(request: Request, upload: RequireUpload):
    return templates.TemplateResponse(request, "partials/upload.html", {"upload": upload})
