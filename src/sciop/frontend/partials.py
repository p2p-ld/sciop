"""Assorted partials that have no other base type"""

from typing import Annotated, Optional

from fastapi import APIRouter, Body, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlmodel import select

from sciop import models
from sciop.api.deps import RequireCurrentAccount, SessionDep
from sciop.frontend.templates import templates
from sciop.models import (
    Account,
    FormAccountScope,
    FormAccountScopeAction,
    ItemScopes,
)

partials_router = APIRouter(prefix="/partials")


@partials_router.get("/model-list", response_class=HTMLResponse)
def model_list(idx: int, field_name: str, model_name: str, form_id: str, request: Request):
    """
    Render a model that is nested within a form using the form-json syntax
    https://github.com/xehrad/form-json
    """
    if not hasattr(models, model_name):
        raise HTTPException(404, f"Model {model_name} not found")
    return templates.TemplateResponse(
        request,
        "partials/model-list.html",
        {
            "form_id": form_id,
            "idx": idx,
            "model_name": model_name,
            "model": getattr(models, model_name),
            "field_name": field_name,
            "field_name_prefix": f"{field_name}[{idx}].",
        },
    )


@partials_router.post("/account-scopes")
async def account_scopes(
    session: SessionDep,
    request: Request,
    current_account: RequireCurrentAccount,
    action: FormAccountScopeAction,
    account_query: Annotated[Optional[str], Body()] = None,
    account_scopes: Optional[list[FormAccountScope]] = None,
    item_slug: Optional[str] = None,
):
    if account_scopes is None:
        account_scopes = []
    else:
        for a in account_scopes:
            a.scopes = [s for s in a.scopes if s != ""]

    if (
        action.action == "add account"
        and account_query
        and account_query.strip() != current_account.username
    ):
        acct = session.exec(
            select(Account).where(
                Account.username == account_query.strip(), Account != current_account
            )
        ).first()
        if acct:
            scopes = []
            if item_slug:
                scopes = [s.scope.value for s in acct.dataset_scopes if s.dataset.slug == item_slug]

            account_scopes.append(FormAccountScope(username=acct.username, scopes=scopes))
    elif action.action == "remove account":
        account_scopes = [a for a in account_scopes if a.username != action.username]
    elif (
        action.action == "add scope"
        and action.scope
        and action.scope in ItemScopes.__members__.values()
    ):
        for i, a in enumerate(account_scopes):
            if a.username == action.username and action.scope not in a.scopes:
                account_scopes[i].scopes.append(action.scope)
    elif action.action == "remove scope":
        for i, a in enumerate(account_scopes):
            if a.username == action.username and action.scope in a.scopes:
                account_scopes[i].scopes.remove(action.scope)

    return templates.TemplateResponse(
        request,
        "partials/accounts.html",
        {"items": account_scopes, "scopes_form": True},
    )
