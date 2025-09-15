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
    AccountScopesRead,
    ItemScopes,
    ItemScopesAction,
    TargetType,
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


@partials_router.get("/whatsnew", response_class=HTMLResponse)
async def whatsnew_items(session: SessionDep, request: Request):
    entries = session.exec(
        select(models.AtomFeedEntry).order_by(models.AtomFeedEntry.updated.desc())
    ).all()
    if not entries:
        entries = []
        updated_date = None
    else:
        updated_date = entries[0].updated

    return templates.TemplateResponse(
        request,
        "partials/whatsnew-entries.html",
        {"entries": entries, "updated_date": updated_date},
    )


@partials_router.get("/report", response_class=HTMLResponse)
async def report_modal(request: Request, target_type: TargetType, target: str):
    """
    Inject a report modal into the `#report-modal-container` element
    """
    return templates.TemplateResponse(
        request,
        "partials/report-modal.html",
        {"target_type": target_type, "target": target},
        headers={"HX-Retarget": "#report-modal-container"},


@partials_router.post("/account-scopes")
async def account_scopes(
    session: SessionDep,
    request: Request,
    current_account: RequireCurrentAccount,
    action: ItemScopesAction,
    editing: Annotated[Optional[bool], Body()] = False,
    account_query: Annotated[Optional[str], Body()] = None,
    account_scopes: Optional[list[AccountScopesRead]] = None,
):
    if account_scopes is None:
        account_scopes = []
    else:
        for acc in account_scopes:
            acc.scopes = [s for s in acc.scopes if s != ""]

    if (
        action.action == "add account"
        and account_query
        and account_query.strip() != current_account.username
        and account_query.strip() not in [s.username for s in account_scopes]
    ):
        acct = session.exec(
            select(Account).where(
                Account.username == account_query.strip(), Account != current_account
            )
        ).first()
        if acct:
            account_scopes.append(AccountScopesRead(username=acct.username, scopes=[]))
    elif (
        action.action == "add scope"
        and action.scope
        and action.scope in ItemScopes.__members__.values()
    ):
        for idx, scope in enumerate(account_scopes):
            if scope.username == action.username and action.scope not in scope.scopes:
                account_scopes[idx].scopes.append(action.scope)
    elif action.action == "remove scope":
        for idx, scope in enumerate(account_scopes):
            if scope.username == action.username and action.scope in scope.scopes:
                account_scopes[idx].scopes.remove(action.scope)

    return templates.TemplateResponse(
        request,
        "partials/accounts.html",
        {
            "items": account_scopes,
            "scopes_form": True,
            "edit": editing,
        },
    )
