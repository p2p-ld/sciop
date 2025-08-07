from typing import Annotated

from fastapi import APIRouter, Query
from sqlmodel import select

from sciop.api.deps import SessionDep
from sciop.frontend.templates import jinja
from sciop.models import Account, Dataset, Tag

autocomplete_router = APIRouter(prefix="/autocomplete", include_in_schema=False)


@autocomplete_router.get("/publisher")
@jinja.hx("partials/autocomplete-options.html")
async def publisher(publisher: str, session: SessionDep) -> list[str]:
    stmt = select(Dataset.publisher).filter(Dataset.publisher.like(f"%{publisher}%"))
    return session.exec(stmt).all()


@autocomplete_router.get("/tags")
@jinja.hx("partials/autocomplete-options.html")
async def tags(session: SessionDep, tags: Annotated[list[str], Query()]) -> list[str]:
    # first is the current query, the rest are existing tokens
    query = tags[0] if tags else ""
    tag_items = []

    # allow tags to be queried both as a comma separated list and as a single token
    if "," in query:
        tag_items = [t.strip() for t in query.split(",")]
        tag_base = ", ".join(tag_items[:-1])
        tag_query = tag_items[-1]
    else:
        tag_base = False
        tag_query = query.strip()

    stmt = select(Tag.tag).filter(
        Tag.tag.like(f"%{tag_query}%"), Tag.tag.not_in(tags[1:] + tag_items[:-1])
    )
    results = session.exec(stmt).all()
    if tag_base:
        results = [", ".join([tag_base, r]) for r in results]
    return results


@autocomplete_router.get("/usernames")
@jinja.hx("partials/autocomplete-options.html")
async def usernames(session: SessionDep, usernames: Annotated[list[str], Query()]) -> list[str]:
    # first is the current query, the rest are existing tokens
    query = (usernames[0] if usernames else "").strip()

    stmt = select(Account.username).filter(
        Account.username.like(f"%{query}%"), Account.username.not_in(usernames[1:])
    )
    results = session.exec(stmt).all()
    return results
