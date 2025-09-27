from typing import Annotated, Optional

from fastapi import APIRouter, Body, Query, Request
from sqlmodel import select

from sciop.api.deps import RequireCurrentAccount, SessionDep
from sciop.frontend.templates import jinja
from sciop.models import Account, Dataset, ItemScopesRead, Tag

autocomplete_router = APIRouter(prefix="/autocomplete", include_in_schema=False)


@autocomplete_router.get("/publisher")
@jinja.hx("partials/autocomplete-options.html")
async def publisher(publisher: str, session: SessionDep) -> list[str]:
    stmt = select(Dataset.publisher).filter(Dataset.publisher.like(f"%{publisher}%"))
    return session.exec(stmt).all()


@autocomplete_router.get("/tags")
@jinja.hx("partials/autocomplete-options.html")
async def tags(
    session: SessionDep,
    tags: Annotated[list[str], Query()],
) -> list[str]:
    tag_items = []
    # first is the current query, the rest are existing tokens
    query = tags[0]

    # allow tags to be queried both as a comma separated list and as a single token
    if "," in query:
        tag_items = [t.strip() for t in query.split(",")]
        tag_base = ", ".join(tag_items[:-1])
        tag_query = tag_items[-1]
    else:
        tag_base = False
        tag_query = query.strip()

    tokens = []

    for tag in tags[1:]:
        if "," in tag:
            tokens.extend([t.strip() for t in tag.split(",")])
        else:
            tokens.append(tag)

    stmt = select(Tag.tag).filter(
        Tag.tag.like(f"%{tag_query}%"), Tag.tag.not_in(tokens + tag_items[:-1])
    )
    results = session.exec(stmt).all()
    if tag_base:
        results = [", ".join([tag_base, r]) for r in results]
    return results


@autocomplete_router.post("/account_scopes")
@jinja.hx("partials/autocomplete-options.html")
async def collaborators(
    session: SessionDep,
    request: Request,
    current_account: RequireCurrentAccount,
    account_query: Annotated[str, Body()],
    account_scopes: Optional[list[ItemScopesRead]] = None,
):
    if not account_scopes:
        account_scopes = []

    stmt = select(Account.username).filter(
        Account.username.like(f"%{account_query.strip()}%"),
        Account.username.not_in([*[s.username for s in account_scopes], current_account.username]),
    )
    results = session.exec(stmt).all()
    return results
