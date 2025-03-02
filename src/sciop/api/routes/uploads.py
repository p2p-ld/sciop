from fastapi import APIRouter, HTTPException
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlmodel import select

from sciop import crud
from sciop.api.deps import (
    CurrentAccount,
    RequireCurrentAccount,
    RequireUpload,
    RequireVisibleUpload,
    SessionDep,
)
from sciop.models import ModerationAction, SuccessResponse, Upload, UploadRead

uploads_router = APIRouter(prefix="/uploads")


@uploads_router.get("/")
async def uploads(session: SessionDep, current_account: CurrentAccount) -> Page[UploadRead]:
    return paginate(
        session,
        select(Upload)
        .where(Upload.visible_to(current_account) == True)
        .order_by(Upload.created_at),
    )


@uploads_router.get("/{infohash}")
async def upload_show(infohash: str, upload: RequireVisibleUpload) -> UploadRead:
    return upload


@uploads_router.delete("/{infohash}")
async def upload_delete(
    infohash: str,
    upload: RequireUpload,
    current_account: RequireCurrentAccount,
    session: SessionDep,
) -> SuccessResponse:
    if not upload.removable_by(current_account):
        raise HTTPException(403, f"Not permitted to remove upload {infohash}")
    upload.is_removed = True
    session.add(upload)
    session.commit()
    crud.log_moderation_action(
        session=session,
        actor=current_account,
        target=upload,
        action=ModerationAction.remove,
    )
    return SuccessResponse(success=True)
