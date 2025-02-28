from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlmodel import select

from sciop.api.deps import RequireTag, SessionDep
from sciop.frontend.templates import jinja, templates
from sciop.models import Dataset, Upload

tags_router = APIRouter(prefix="/tags")


@tags_router.get("/{tag}", response_class=HTMLResponse)
def tag_show(tag: str, tag_obj: RequireTag, request: Request):
    return templates.TemplateResponse(
        request,
        "pages/tag.html",
        {
            "tag": tag_obj,
        },
    )


@tags_router.get("/{tag}/datasets", response_class=HTMLResponse)
@jinja.hx("partials/datasets.html")
def tag_datasets(
    tag: str, tag_obj: RequireTag, session: SessionDep, request: Request
) -> Page[Dataset]:
    stmt = select(Dataset).where(Dataset.is_approved == True, Dataset.tags.any(tag=tag))
    return paginate(conn=session, query=stmt)


@tags_router.get("/{tag}/uploads", response_class=HTMLResponse)
@jinja.hx("partials/uploads.html")
def tag_uploads(
    tag: str, tag_obj: RequireTag, session: SessionDep, request: Request
) -> Page[Upload]:
    stmt = select(Upload).join(Dataset).where(Dataset.tags.any(tag=tag), Upload.is_approved == True)
    return paginate(conn=session, query=stmt)
