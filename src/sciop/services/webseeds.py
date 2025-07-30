"""
Implementation notes:

- On using https concurrently: https://github.com/encode/httpx/discussions/2662
- https://www.python-httpx.org/advanced/resource-limits/
"""

import asyncio
import random

from httpx import AsyncClient, Limits, Response
from pydantic import BaseModel
from torrent_models import Torrent, TorrentVersion
from torrent_models.types.v1 import V1PieceRange
from torrent_models.types.v2 import V2PieceRange

from sciop import crud
from sciop.config import get_config
from sciop.config.services import WebseedValidationConfig
from sciop.db import get_session


class WebseedValidationResult(BaseModel):
    infohash: str
    url: str
    valid: bool
    message: str | None = None


def validate_webseed(infohash: str, url: str) -> WebseedValidationResult:
    cfg = get_config()
    ws_config = cfg.services.webseed_validation
    if not ws_config.enabled:
        if ws_config.enable_adding_webseeds:
            return WebseedValidationResult(infohash=infohash, url=url, valid=True)
        else:
            return WebseedValidationResult(infohash=infohash, url=url, valid=False)

    with next(get_session()) as session:
        torrent_file = crud.get_torrent_from_infohash(session=session, infohash=infohash)
        if not torrent_file:
            raise ValueError(f"Torrent with infohash {infohash} not found")

    torrent = Torrent.read(torrent_file.filesystem_path)
    n_pieces = ws_config.get_n_pieces(torrent.info.piece_length)
    loop = asyncio.get_event_loop()
    if torrent.torrent_version == TorrentVersion.v1:
        return loop.run_until_complete(_validate_v1(torrent, url, n_pieces, ws_config))
    else:
        return loop.run_until_complete(_validate_v2(torrent, url, n_pieces, ws_config))


async def _validate_v1(
    torrent: Torrent, url: str, n_pieces: int, config: WebseedValidationConfig
) -> WebseedValidationResult:
    piece_indices = random.sample(range(len(torrent.info.pieces)), n_pieces)
    ranges = [torrent.v1_piece_range(idx) for idx in piece_indices]
    async with _get_client(config) as client:
        _ = asyncio.gather(*[_validate_range_v1(r, url, client) for r in ranges])
        # TODO: ...


async def _validate_v2(
    torrent: Torrent, url: str, n_pieces: int, config: WebseedValidationConfig
) -> WebseedValidationResult:
    ranges = _pick_v2_ranges(torrent, n_pieces)
    async with _get_client(config) as client:
        _ = asyncio.gather(*[_validate_range_v2(r, url, client) for r in ranges])
        # TODO ...


async def _validate_range_v1(
    range: V1PieceRange, url: str, client: AsyncClient
) -> tuple[bool, Response]:
    raise NotImplementedError()


async def _validate_range_v2(
    range: V2PieceRange, url: str, client: AsyncClient
) -> tuple[bool, Response]:
    raise NotImplementedError()


def _pick_v2_ranges(torrent: Torrent, n_pieces: int) -> list[V2PieceRange]:
    ranges: list[V2PieceRange] = []

    total_pieces = len(
        [
            path
            for path, file_item in torrent.flat_files
            if file_item["length"] < torrent.info.piece_length
        ]
    ) + len(torrent.piece_layers)
    while len(ranges) < n_pieces and len(ranges) < total_pieces:
        path = random.choice(list(torrent.flat_files.keys()))
        file_item = torrent.flat_files[path]
        piece_idx = random.randint(0, file_item["length"] // torrent.info.piece_length)
        if any([r.path == path and r.piece_idx == piece_idx for r in ranges]):
            continue
        ranges.append(torrent.v2_piece_range(path, piece_idx))
    return ranges


def _get_client(config: WebseedValidationConfig) -> AsyncClient:
    cfg = get_config()
    return AsyncClient(
        limits=Limits(max_connections=config.max_connections),
        headers={"User Agent": cfg.server.user_agent},
    )
