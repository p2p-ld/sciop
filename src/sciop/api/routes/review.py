from fastapi import APIRouter

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
from sciop.models import ModerationAction, Scope, SuccessResponse

review_router = APIRouter()


@review_router.post("/datasets/{dataset_slug}/approve")
async def approve_dataset(
    dataset_slug: str, account: RequireReviewer, session: SessionDep, dataset: RequireDataset
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


@review_router.post("/accounts/{username}/scopes/{scope}")
async def grant_account_scope(
    username: str,
    scope: ValidScope,
    current_account: RequireAdmin,
    account: RequireAccount,
    session: SessionDep,
):

    if not account.has_scope(scope):
        account.scopes.append(Scope(name=scope))
        session.add(account)
        session.commit()
    return SuccessResponse(success=True)


@review_router.delete("/accounts/{username}/scopes/{scope}")
async def revoke_account_scope(
    username: str,
    scope: ValidScope,
    current_account: RequireAdmin,
    account: RequireAccount,
    session: SessionDep,
):
    if scope := account.get_scope(scope):
        account.scopes.remove(scope)
        session.add(account)
        session.commit()
    return SuccessResponse(success=True)
