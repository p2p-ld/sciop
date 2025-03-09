from fastapi import APIRouter
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlmodel import func, select, text

from sciop.api.deps import SessionDep
from sciop.frontend.templates import jinja
from sciop.models import Dataset, Tag, TagSummary, Upload

tags_router = APIRouter(prefix="/tags")


@tags_router.get("/")
async def tags_show() -> Page[Tag]:
    raise NotImplementedError("Paging through all tags is not implemented yet")


@tags_router.get("/search")
@jinja.hx("partials/tags.html")
async def tags_search(query: str = None, session: SessionDep = None) -> Page[TagSummary]:
    subq = (
        select(func.count(Upload.upload_id))
        .filter(Dataset.dataset_id == Upload.dataset_id, Upload.is_visible == True)
        .correlate(Dataset)
        .scalar_subquery()
    )
    stmt = (
        select(
            Tag.tag,
            func.count(Dataset.dataset_id).label("n_datasets"),
            func.sum(subq).label("n_uploads"),
        )
        .join(Tag.datasets)
        .group_by(Tag.tag_id)
        # string interpolation fine here, sqlalchemy injects it as a parameter
        .filter(
            Tag.tag.like(f"%{query}%"),
            Dataset.tags.any(Tag.tag.like(f"%{query}%")),
            Dataset.is_visible == True,
        )
        .order_by(text("n_uploads DESC"))
    )

    count_stmt = select(func.count(Tag.tag_id)).filter(Tag.tag.like(f"%{query}%"))
    return paginate(conn=session, query=stmt, count_query=count_stmt)
