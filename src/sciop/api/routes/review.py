from fastapi import APIRouter, HTTPException, Response

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
from sciop.models import ModerationAction, Scope, SuccessResponse, Scopes

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


@review_router.post("/uploads/{short_hash}/approve")
async def approve_upload(
    short_hash: str, account: RequireReviewer, session: SessionDep, upload: RequireUpload
) -> SuccessResponse:
    upload.enabled = True
    session.add(upload)
    session.commit()

    crud.log_moderation_action(
        session=session, actor=account, action=ModerationAction.approve, target=upload
    )
    return SuccessResponse(success=True)


@review_router.post("/uploads/{short_hash}/deny")
async def deny_upload(
    short_hash: str, account: RequireReviewer, session: SessionDep, upload: RequireUpload
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
        raise HTTPException(403, "The root scope cannot be modified")
    if  not current_account.get_scope('root') and scope_name == "admin":
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
        raise HTTPException(403, "The root scope cannot be modified")
    if  not current_account.get_scope('root') and scope_name == "admin":
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
