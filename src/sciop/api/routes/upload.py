from datetime import timedelta
from typing import Annotated
from hashlib import blake2b

from fastapi import APIRouter, Form, HTTPException, Response, UploadFile
from torf import Torrent

from sciop import crud
from sciop.api.auth import create_access_token
from sciop.api.deps import SessionDep, RequireReviewer, RequireUploader
from sciop.config import config
from sciop.models import (
    Account,
    AccountCreate,
    Token,
    Dataset,
    SuccessResponse,
    TorrentFileCreate,
    FileInTorrentCreate,
    TorrentFile,
    TorrentFileRead,
)
from sciop.logging import init_logger

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
    Upload a torrent file prior to creating a Dataset Instance
    """
    torrent = Torrent.read_stream(file.file)
    torrent.validate()
    await file.seek(0)
    hash = _hash_file(file)
    existing_torrent = crud.get_torrent_from_hash(session=session, hash=hash)
    if existing_torrent:
        # FIXME: Handle duplicate torrent files
        # raise HTTPException(
        #     status_code=400,
        #     detail="An identical torrent file already exists!",
        # )
        pass
    created_torrent = TorrentFileCreate(
        file_name=file.filename,
        hash=hash,
        short_hash=hash[0:8],
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

    created_torrent = crud.create_torrent(
        session=session, created_torrent=created_torrent, account=account
    )

    return TorrentFileRead.model_validate(created_torrent)
