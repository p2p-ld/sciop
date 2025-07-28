from pathlib import Path
from typing import Annotated, Any
from typing import Literal as L

from fastapi import APIRouter, HTTPException, Query, UploadFile
from pydantic import ValidationError
from starlette.requests import Request
from starlette.responses import Response
from torrent_models import Torrent

from sciop import crud
from sciop.api.deps import RequireCurrentAccount, SessionDep
from sciop.frontend.templates import jinja
from sciop.logging import init_logger
from sciop.middleware import limiter
from sciop.models import FileInTorrentCreate, TorrentFileCreate, TorrentFileRead

torrents_router = APIRouter(prefix="/torrents")
torrents_logger = init_logger("api.torrents")


def _passthrough(
    *, route_result: TorrentFileRead, route_context: Any = None
) -> dict[L["torrent"], TorrentFileRead]:
    return {"torrent": route_result}


@torrents_router.post("/")
@limiter.limit("60/minute;1000/hour")
@jinja.hx("partials/torrent.html", make_context=_passthrough)
async def upload_torrent(
    request: Request,
    response: Response,
    account: RequireCurrentAccount,
    file: UploadFile,
    session: SessionDep,
    force: Annotated[
        bool,
        Query(
            description="If an existing torrent with matching infohash exists, "
            "and we can edit it, replace it."
        ),
    ] = False,
) -> TorrentFileRead:
    """
    Upload a torrent file prior to creating a Dataset upload
    """
    torrents_logger.debug("Processing torrent file")
    try:
        torrent = Torrent.read_stream(file.file)
    except ValidationError:
        torrents_logger.exception("Error decoding upload")
        raise HTTPException(
            status_code=415,
            detail="Could not decode upload, is this a .torrent file?",
        ) from None

    creating_account = account
    existing_upload = None
    existing_torrent = crud.get_torrent_from_infohash(
        session=session, v1=torrent.v1_infohash, v2=torrent.v2_infohash
    )
    if existing_torrent:
        if existing_torrent.upload is not None:
            if not force:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "msg": "An identical torrent file already exists "
                        "and is associated with an upload: "
                        f'<a href="/uploads/{existing_torrent.infohash}">'
                        f"{existing_torrent.infohash}"
                        "</a>",
                        "raw_html": True,
                    },
                )
            elif force and existing_torrent.upload.editable_by(account):
                torrents_logger.info(
                    f"Replacing existing torrent with another that matches infohash "
                    f"{existing_torrent.infohash}"
                )
                # preserve the original creator of the upload when the infohash is unchanged
                creating_account = existing_torrent.upload.account
                existing_upload = existing_torrent.upload
                session.delete(existing_torrent)
                session.commit()
            else:
                raise HTTPException(
                    status_code=403,
                    detail={
                        "msg": "An identical torrent file already exists "
                        "and is associated with an upload: "
                        f'<a href="/uploads/{existing_torrent.infohash}">'
                        f"{existing_torrent.infohash}"
                        "</a> and current account does not have permissions to edit it",
                        "raw_html": True,
                    },
                )
        else:
            torrents_logger.debug("Replacing existing orphaned torrent with new torrent")
            session.delete(existing_torrent)
            session.commit()

    trackers = [tracker for tier in torrent.flat_trackers for tracker in tier]
    if len(trackers) == 0:
        raise HTTPException(
            status_code=400,
            detail={
                "msg": (
                    "Uploaded torrents must contain at least one tracker. "
                    'See the <a href="/docs/uploading/trackers/#default-trackers">'
                    "default trackers list.</a>"
                ),
                "raw_html": True,
            },
        )

    created_torrent = TorrentFileCreate(
        file_name=file.filename,
        v1_infohash=torrent.v1_infohash if torrent.v1_infohash else None,
        v2_infohash=torrent.v2_infohash if torrent.v2_infohash else None,
        version=torrent.torrent_version,
        total_size=torrent.total_size,
        piece_size=torrent.info.piece_length,
        files=[FileInTorrentCreate(path=_file.path, size=_file.length) for _file in torrent.files],
        announce_urls=trackers,
    )

    torrents_logger.debug("Writing torrent file to disk")
    created_torrent.filesystem_path.parent.mkdir(parents=True, exist_ok=True)
    await file.seek(0)
    with open(created_torrent.filesystem_path, "wb") as f:
        data = await file.read()
        f.write(data)

    created_torrent.torrent_size = Path(created_torrent.filesystem_path).stat().st_size
    torrents_logger.debug("Creating torrent file in db")
    created_torrent = crud.create_torrent(
        session=session, created_torrent=created_torrent, account=creating_account
    )
    if existing_upload:
        existing_upload.torrent = created_torrent
        session.add(existing_upload)
        session.commit()

    return TorrentFileRead.model_validate(created_torrent)
