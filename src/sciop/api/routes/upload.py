from hashlib import blake2b
from pathlib import Path
from typing import Any
from typing import Literal as L

from fastapi import APIRouter, HTTPException, UploadFile
from starlette.requests import Request
from starlette.responses import Response
from torf import BdecodeError, MetainfoError

from sciop import crud
from sciop.api.deps import RequireCurrentAccount, SessionDep
from sciop.frontend.templates import jinja
from sciop.logging import init_logger
from sciop.middleware import limiter
from sciop.models import (
    FileInTorrentCreate,
    Torrent,
    TorrentFileCreate,
    TorrentFileRead,
)

upload_router = APIRouter(prefix="/upload")
upload_logger = init_logger("api.upload")


def _hash_file(file: UploadFile) -> str:
    hasher = blake2b(digest_size=32)
    hasher.update(file.file.read())
    return hasher.hexdigest()


def _passthrough(
    *, route_result: TorrentFileRead, route_context: Any = None
) -> dict[L["torrent"], TorrentFileRead]:
    return {"torrent": route_result}


@upload_router.post("/torrent")
@limiter.limit("60/minute;1000/hour")
@jinja.hx("partials/torrent.html", make_context=_passthrough)
async def upload_torrent(
    request: Request,
    response: Response,
    account: RequireCurrentAccount,
    file: UploadFile,
    session: SessionDep,
) -> TorrentFileRead:
    """
    Upload a torrent file prior to creating a Dataset upload
    """
    upload_logger.debug("Processing torrent file")
    try:
        torrent = Torrent.read_stream(file.file)
        torrent.validate()
    except BdecodeError:
        upload_logger.exception("Error decoding upload")
        raise HTTPException(
            status_code=415,
            detail="Could not decode upload, is this a .torrent file?",
        ) from None
    except MetainfoError as e:
        raise HTTPException(status_code=415, detail=f"MetaInfo invalid: {str(e)}") from None

    existing_torrent = crud.get_torrent_from_infohash(
        session=session, v1=torrent.infohash, v2=torrent.v2_infohash
    )
    if existing_torrent:
        if existing_torrent.upload is not None:
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
        else:
            upload_logger.debug("Replacing existing orphaned torrent with new torrent")
            session.delete(existing_torrent)
            session.commit()

    trackers = [tracker for tier in torrent.trackers for tracker in tier]
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
        v1_infohash=torrent.infohash,
        v2_infohash=torrent.v2_infohash,
        version=torrent.torrent_version,
        total_size=torrent.size,
        piece_size=torrent.piece_size,
        files=[FileInTorrentCreate(path=_file.path, size=_file.size) for _file in torrent.files],
        announce_urls=trackers,
    )

    upload_logger.debug("Writing torrent file to disk")
    created_torrent.filesystem_path.parent.mkdir(parents=True, exist_ok=True)
    await file.seek(0)
    with open(created_torrent.filesystem_path, "wb") as f:
        data = await file.read()
        f.write(data)

    created_torrent.torrent_size = Path(created_torrent.filesystem_path).stat().st_size
    upload_logger.debug("Creating torrent file in db")
    created_torrent = crud.create_torrent(
        session=session, created_torrent=created_torrent, account=account
    )

    return TorrentFileRead.model_validate(created_torrent)
