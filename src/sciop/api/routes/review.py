from fastapi import APIRouter, HTTPException, Request, Response
from sqlmodel import select

from sciop import crud
from sciop.api.deps import (
    RequireAccount,
    RequireAdmin,
    RequireDataset,
    RequireReviewer,
    RequireUpload,
    SessionDep,
    ValidScope,
)
from sciop.frontend.templates import jinja
from sciop.middleware import limiter
from sciop.models import ModerationAction, Scope, SuccessResponse
from sciop.models.mixin import _Friedolin

review_router = APIRouter()


@review_router.post("/datasets/{dataset_slug}/approve")
async def approve_dataset(
    dataset_slug: str,
    account: RequireReviewer,
    session: SessionDep,
    dataset: RequireDataset,
    response: Response,
) -> SuccessResponse:
    dataset.enabled = True
    session.add(dataset)
    session.commit()

    crud.log_moderation_action(
        session=session, actor=account, action=ModerationAction.approve, target=dataset
    )
    return SuccessResponse(success=True)


@review_router.post("/datasets/{dataset_slug}/deny")
async def deny_dataset(
    dataset_slug: str, account: RequireReviewer, session: SessionDep, dataset: RequireDataset
) -> SuccessResponse:

    session.delete(dataset)
    session.commit()

    crud.log_moderation_action(
        session=session, actor=account, action=ModerationAction.deny, target=dataset
    )
    return SuccessResponse(success=True)


@review_router.post("/uploads/{infohash}/approve")
async def approve_upload(
    infohash: str, account: RequireReviewer, session: SessionDep, upload: RequireUpload
) -> SuccessResponse:
    upload.enabled = True
    session.add(upload)
    session.commit()

    crud.log_moderation_action(
        session=session, actor=account, action=ModerationAction.approve, target=upload
    )
    return SuccessResponse(success=True)


@review_router.post("/uploads/{infohash}/deny")
async def deny_upload(
    infohash: str, account: RequireReviewer, session: SessionDep, upload: RequireUpload
) -> SuccessResponse:
    session.delete(upload)
    session.commit()
    crud.log_moderation_action(
        session=session, actor=account, action=ModerationAction.deny, target=upload
    )
    return SuccessResponse(success=True)


@review_router.delete("/accounts/{username}")
async def suspend_account(
    username: str, account: RequireAccount, session: SessionDep, current_account: RequireAdmin
) -> SuccessResponse:
    if account.id == current_account.id:
        raise HTTPException(403, "You cannot suspend yourself")
    session.delete(account)
    session.commit()
    crud.log_moderation_action(
        session=session, actor=current_account, action=ModerationAction.suspend, target=account
    )
    return SuccessResponse(success=True)


@review_router.put("/accounts/{username}/scopes/{scope_name}")
@jinja.hx("partials/scope-toggle-button.html")
async def grant_account_scope(
    username: str,
    scope_name: ValidScope,
    current_account: RequireAdmin,
    account: RequireAccount,
    session: SessionDep,
):
    if scope_name == "root":
        if not current_account.get_scope("root"):
            raise HTTPException(403, "Only root can change root permissions.")
        elif account.account_id == current_account.account_id:
            raise HTTPException(403, "You already have root permissions.")
    elif scope_name == "admin" and not current_account.get_scope("root"):
        raise HTTPException(403, "Only root can change admin permissions.")

    if not account.has_scope(scope_name):
        account.scopes.append(Scope.get_item(scope_name, session))
        session.add(account)
        session.commit()

    crud.log_moderation_action(
        session=session,
        actor=current_account,
        action=ModerationAction.add_scope,
        target=account,
        value=scope_name,
    )
    return SuccessResponse(
        success=True, extra={"username": account.username, "scope_name": scope_name}
    )


@review_router.delete("/accounts/{username}/scopes/{scope_name}")
@jinja.hx("partials/scope-toggle-button.html")
async def revoke_account_scope(
    username: str,
    scope_name: ValidScope,
    current_account: RequireAdmin,
    account: RequireAccount,
    session: SessionDep,
):
    if scope_name == "root":
        if not current_account.get_scope("root"):
            raise HTTPException(403, "Only root can change root permissions.")
        elif account.account_id == current_account.account_id:
            raise HTTPException(403, "You cannot remove root scope from yourself.")
    elif scope_name == "admin" and not current_account.get_scope("root"):
        raise HTTPException(403, "Only root can change admin permissions.")

    if scope := account.get_scope(scope_name):
        account.scopes.remove(scope)
        session.add(account)
        session.commit()

    crud.log_moderation_action(
        session=session,
        actor=current_account,
        action=ModerationAction.remove_scope,
        target=account,
        value=scope_name,
    )
    return SuccessResponse(
        success=True, extra={"username": account.username, "scope_name": scope_name}
    )


@review_router.get(
    "/freidolin",
)
@limiter.limit("1/7days")
async def freidolin(request: Request, response: Response, session: SessionDep) -> _Friedolin:
    """use it wisely"""
    data = session.exec(select(_Friedolin)).first()
    return data
