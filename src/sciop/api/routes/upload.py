from hashlib import blake2b
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile

from sciop import crud
from sciop.api.deps import RequireUploader, SessionDep
from sciop.logging import init_logger
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


@upload_router.post("/torrent")
async def upload_torrent(
    account: RequireUploader, file: UploadFile, session: SessionDep
) -> TorrentFileRead:
    """
    Upload a torrent file prior to creating a Dataset upload
    """
    upload_logger.debug("Processing torrent file")
    torrent = Torrent.read_stream(file.file)
    torrent.validate()
    existing_torrent = crud.get_torrent_from_infohash(
        session=session, v1=torrent.infohash, v2=torrent.v2_infohash
    )
    if existing_torrent:
        raise HTTPException(
            status_code=400,
            detail="An identical torrent file already exists!",
        )

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
        trackers=trackers,
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
