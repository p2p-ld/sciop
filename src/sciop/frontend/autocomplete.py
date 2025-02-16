from fastapi import APIRouter
from sqlmodel import select

from sciop.api.deps import SessionDep
from sciop.frontend.templates import jinja
from sciop.models import Dataset, Tag

autocomplete_router = APIRouter(prefix="/autocomplete", include_in_schema=False)


@autocomplete_router.get("/publisher")
@jinja.hx("partials/autocomplete-options.html")
async def publisher(publisher: str, session: SessionDep) -> list[str]:
    stmt = select(Dataset.publisher).filter(Dataset.publisher.like(f"%{publisher}%"))
    return session.exec(stmt).all()


@autocomplete_router.get("/tags")
@jinja.hx("partials/autocomplete-options.html")
async def tags(tags: str, session: SessionDep) -> list[str]:
    # allow tags to be queried both as a comma separated list and as a single token
    if "," in tags:
        tag_items = [t.strip() for t in tags.split(",")]
        tag_base = ", ".join(tag_items[:-1])
        tag_query = tag_items[-1]
    else:
        tag_base = False
        tag_query = tags.strip()

    stmt = select(Tag.tag).filter(Tag.tag.like(f"%{tag_query}%"))
    results = session.exec(stmt).all()
    if tag_base:
        results = [", ".join([tag_base, r]) for r in results]
    return results
