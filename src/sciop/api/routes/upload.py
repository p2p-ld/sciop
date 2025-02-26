from hashlib import blake2b
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile

from sciop import crud
from sciop.api.deps import RequireUploader, SessionDep
from sciop.models import (
    FileInTorrentCreate,
    Torrent,
    TorrentFileCreate,
    TorrentFileRead,
)

upload_router = APIRouter(prefix="/upload")


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

    created_torrent = TorrentFileCreate(
        file_name=file.filename,
        v1_infohash=torrent.infohash,
        v2_infohash=torrent.v2_infohash,
        version=torrent.torrent_version,
        total_size=torrent.size,
        piece_size=torrent.piece_size,
        files=[FileInTorrentCreate(path=str(_file), size=_file.size) for _file in torrent.files],
        trackers=[tracker for tier in torrent.trackers for tracker in tier],
    )

    created_torrent.filesystem_path.parent.mkdir(parents=True, exist_ok=True)
    await file.seek(0)
    with open(created_torrent.filesystem_path, "wb") as f:
        data = await file.read()
        f.write(data)

    created_torrent.torrent_size = Path(created_torrent.filesystem_path).stat().st_size

    created_torrent = crud.create_torrent(
        session=session, created_torrent=created_torrent, account=account
    )

    return TorrentFileRead.model_validate(created_torrent)
