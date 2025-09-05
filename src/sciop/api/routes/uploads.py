from typing import Annotated

from fastapi import APIRouter, Body, HTTPException
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlmodel import select
from starlette.requests import Request
from starlette.responses import Response

from sciop import crud
from sciop.api.deps import (
    CurrentAccount,
    RaggedQueryNoCurrentUrl,
    RequireCurrentAccount,
    RequireEditableBy,
    RequireUpload,
    RequireVisibleUpload,
    SessionDep,
)
from sciop.config import get_config
from sciop.frontend.templates import jinja
from sciop.logging import init_logger
from sciop.models import (
    FileInTorrent,
    FileInTorrentRead,
    ModerationAction,
    RaggedSearchPage,
    SuccessResponse,
    TorrentFile,
    Upload,
    UploadCreate,
    UploadRead,
    UploadUpdate,
    Webseed,
    WebseedCreate,
    WebseedRead,
)
from sciop.scheduler import queue_job
from sciop.types import MaxLenURL

uploads_router = APIRouter(prefix="/uploads")


@uploads_router.get("/")
async def uploads(session: SessionDep, current_account: CurrentAccount) -> Page[UploadRead]:
    return paginate(
        session,
        select(Upload)
        .where(Upload.visible_to(current_account) == True)
        .order_by(Upload.created_at),
    )


@uploads_router.post("/")
async def create_upload(
    session: SessionDep, upload: UploadCreate, current_account: RequireCurrentAccount
) -> UploadRead:
    """
    Create an upload from an already-uploaded torrent's infohash, and
    a dataset (and optionally dataset part(s)) to attach it to.
    """
    torrent = crud.get_torrent_from_infohash(session=session, infohash=upload.infohash)
    if not torrent:
        raise HTTPException(
            status_code=404,
            detail=f"No torrent with short hash {upload.infohash} exists, " "upload it first!",
        )
    dataset = crud.get_visible_dataset(
        session=session, dataset_slug=upload.dataset_slug, account=current_account
    )
    if not dataset:
        raise HTTPException(
            status_code=404,
            detail=f"No dataset {upload.dataset_slug} exists.",
        )
    created_upload = crud.create_upload(
        session=session, created_upload=upload, dataset=dataset, account=current_account
    )
    return created_upload


@uploads_router.get("/{infohash}")
async def upload_show(infohash: str, upload: RequireVisibleUpload) -> UploadRead:
    return upload


@uploads_router.patch("/{infohash}")
async def upload_edit(
    infohash: str,
    upload: RequireVisibleUpload,
    upload_patch: Annotated[UploadUpdate, Body()],
    current_account: RequireEditableBy,
    session: SessionDep,
    request: Request,
    response: Response,
) -> UploadRead:
    """Edit an upload!"""
    updated_upload = upload.update(session, new=upload_patch, commit=True)
    if "HX-Request" in request.headers:
        response.headers["HX-Redirect"] = f"/uploads/{upload.infohash}"
    return updated_upload


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


@uploads_router.get("/{infohash}/files")
@jinja.hx("partials/files.html")
async def upload_files(
    infohash: str,
    upload: RequireVisibleUpload,
    session: SessionDep,
    request: Request,
    response: Response,
    search: RaggedQueryNoCurrentUrl,
) -> RaggedSearchPage[FileInTorrentRead]:
    """
    Files in a torrent file.

    We don't order by path by default,
    since v1 torrents can have their file list in an arbitrary order,
    and that's meaningful for hashing since piece hashes can span multiple files.
    (Sorting by path can be done with the standard `sort` query params, though).
    """
    stmt = (
        select(FileInTorrent)
        .join(FileInTorrent.torrent)
        .where(TorrentFile.upload_id == upload.upload_id)
        .order_by(FileInTorrent.file_in_torrent_id)
    )
    if search.query:
        raise HTTPException(400, "Search query not supported for torrent files")
    request.state.upload = upload
    stmt = search.apply_sort(stmt, FileInTorrent)
    return paginate(conn=session, query=stmt)


@uploads_router.get("/{infohash}/webseeds")
@jinja.hx("partials/webseeds.html")
async def webseeds(
    infohash: str,
    upload: RequireVisibleUpload,
    current_account: CurrentAccount,
    session: SessionDep,
) -> list[WebseedRead]:
    """Show webseeds in a torrent"""
    return session.exec(
        select(Webseed).where(
            Webseed.torrent == upload.torrent,
            Webseed.visible_to(current_account) == True,
        )
    ).all()


@uploads_router.post("/{infohash}/webseeds")
async def create_webseed(
    infohash: str,
    webseed: WebseedCreate,
    upload: RequireVisibleUpload,
    current_account: RequireCurrentAccount,
    session: SessionDep,
    request: Request,
    response: Response,
) -> WebseedRead:
    """Create a new webseed"""
    cfg = get_config()
    if not cfg.services.webseed_validation.enable_adding_webseeds:
        raise HTTPException(403, "Adding webseeds is disabled")
    ws = crud.create_webseed(
        session=session, account=current_account, torrent=upload.torrent, webseed_create=webseed
    )
    if not ws.needs_review:
        queue_job("validate_webseed", kwargs={"infohash": upload.torrent.infohash, "url": ws.url})
    if "HX-Request" in request.headers and "review" not in request.headers.get("HX-Current-URL"):
        response.headers["HX-Refresh"] = "true"
    return WebseedRead.model_validate(ws, update={"account": current_account})


@uploads_router.delete("/{infohash}/webseeds")
async def delete_webseed(
    infohash: str,
    url: MaxLenURL,
    upload: RequireVisibleUpload,
    current_account: RequireCurrentAccount,
    session: SessionDep,
) -> Response:
    """
    Delete a webseed

    Webseeds can be deleted by

    - the account that created them
    - the uploader of the torrent
    - a account with review permissions
    """
    webseed = WebseedCreate(url=url)
    logger = init_logger("api.uploads.webseeds")
    logger.debug("Deleting webseed %s for %s", webseed.url, upload.infohash)
    ws = crud.get_webseed(session=session, infohash=infohash, url=webseed.url)
    if not ws:
        raise HTTPException(404, f"No webseed {webseed.url} for torrent {infohash}")
    elif not ws.removable_by(current_account):
        raise HTTPException(
            403, f"Not permitted to remove webseed {webseed.url} for torrent {infohash}"
        )
    crud.log_moderation_action(
        session=session, actor=current_account, target=ws, action=ModerationAction.remove
    )
    session.delete(ws)
    session.commit()

    return Response(status_code=200)
