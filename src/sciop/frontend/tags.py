from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlmodel import select

from sciop.api.deps import CurrentAccount, RequireTag, SessionDep
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


@tags_router.get("/{tag}/datasets")
@jinja.hx("partials/datasets.html")
def tag_datasets(
    tag: str,
    tag_obj: RequireTag,
    session: SessionDep,
    request: Request,
    current_account: CurrentAccount,
) -> Page[Dataset]:
    stmt = (
        select(Dataset)
        .where(Dataset.visible_to(current_account) == True, Dataset.tags.any(tag=tag))
        .order_by(Dataset.created_at.desc())
    )
    return paginate(conn=session, query=stmt)


@tags_router.get("/{tag}/uploads")
@jinja.hx("partials/uploads.html")
def tag_uploads(
    tag: str,
    tag_obj: RequireTag,
    session: SessionDep,
    request: Request,
    current_account: CurrentAccount,
) -> Page[Upload]:
    stmt = (
        select(Upload)
        .join(Dataset)
        .where(Dataset.tags.any(tag=tag), Upload.visible_to(current_account) == True)
        .order_by(Upload.created_at.desc())
    )
    return paginate(conn=session, query=stmt)
