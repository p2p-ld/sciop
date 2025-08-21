"""
Implementation notes:

- On using https concurrently: https://github.com/encode/httpx/discussions/2662
- https://www.python-httpx.org/advanced/resource-limits/
"""

import asyncio
import random
from collections.abc import Coroutine
from typing import Any, Callable, Literal

from httpx import AsyncClient, Limits, ReadTimeout, TimeoutException
from pydantic import BaseModel
from sqlmodel import Session
from torrent_models import Torrent, TorrentVersion
from torrent_models.const import BLOCK_SIZE
from torrent_models.types.v1 import FileItemRange, V1PieceRange
from torrent_models.types.v2 import V2PieceRange

from sciop.config import get_config
from sciop.exceptions import WebseedHTTPError, WebseedValidationError
from sciop.logging import init_logger


class WebseedValidationResult(BaseModel):
    infohash: str
    url: str
    valid: bool
    error_type: Literal["http", "validation", "timeout"] | None = None
    message: str | None = None
    ranges: list[V1PieceRange] | list[V2PieceRange] | None = None


async def validate_webseed_service(infohash: str, url: str, session: Session) -> None:
    """
    Service wrapper for validating webseeds.
    Handles updating the database objects with the results of the validation.
    """
    from sciop import crud
    from sciop.models import WebseedStatus

    cfg = get_config()
    logger = init_logger("jobs.validate_webseed")
    logger.info("Validating webseed %s for torrent %s", url, infohash)
    webseed = crud.get_webseed(session=session, infohash=infohash, url=url)
    if not webseed:
        msg = f"No webseed with url {url} found for torrent {infohash}"
        logger.exception(msg)
        raise RuntimeError(msg)
    if webseed.status == "in_progress":
        logger.debug("Webseed is being validated by another process")
        return

    ws_config = cfg.services.webseed_validation
    if not ws_config.enabled:
        logger.debug("Validation disabled. Marking valid without validating")
        webseed.status = WebseedStatus.validated
        webseed.message = "Not validated - validation was disabled"
        session.add(webseed)
        session.commit()
        return

    try:
        webseed.status = WebseedStatus.in_progress
        session.add(webseed)
        session.commit()
        res = await validate_webseed(infohash=infohash, url=url, session=session)
    except Exception as e:
        logger.exception(f"Exception while validating webseed {url} for {infohash}: {e}")
        webseed.status = WebseedStatus.error
        webseed.message = str(e)
        session.add(webseed)
        session.commit()
        raise

    if res.valid:
        webseed.status = WebseedStatus.validated
        logger.info("Webseed validation successful for %s for torrent %s", url, infohash)
    else:
        msg = f"{res.error_type} - {res.message}"
        logger.info("Webseed validation failed for %s for torrent %s\n%s", url, infohash, msg)
        webseed.status = WebseedStatus.error
        webseed.message = f"{res.error_type} - {res.message}"
    session.add(webseed)
    session.commit()


async def validate_webseed(infohash: str, url: str, session: Session) -> WebseedValidationResult:
    from sciop import crud

    cfg = get_config()
    ws_config = cfg.services.webseed_validation

    torrent_file = crud.get_torrent_from_infohash(session=session, infohash=infohash)
    if not torrent_file:
        raise ValueError(f"Torrent with infohash {infohash} not found")

    torrent = Torrent.read(torrent_file.filesystem_path)
    n_pieces = ws_config.get_max_n_pieces(torrent.info.piece_length)
    if torrent.torrent_version == TorrentVersion.v1:
        return await _validate_v1(torrent, url, n_pieces)
    else:
        return await _validate_v2(torrent, url, n_pieces)


async def _validate_v1(torrent: Torrent, url: str, n_pieces: int) -> WebseedValidationResult:
    piece_indices = random.sample(
        range(len(torrent.info.pieces)), min(n_pieces, len(torrent.info.pieces))
    )
    ranges = [torrent.v1_piece_range(idx) for idx in piece_indices]
    async with _get_client() as client:
        return await _validate_ranges(_validate_range_v1, ranges, url, torrent.v1_infohash, client)


async def _validate_v2(torrent: Torrent, url: str, n_pieces: int) -> WebseedValidationResult:
    ranges = _pick_v2_ranges(torrent, n_pieces)
    async with _get_client() as client:
        return await _validate_ranges(_validate_range_v2, ranges, url, torrent.v2_infohash, client)


async def _validate_ranges(
    fn: Callable[[V2PieceRange | V1PieceRange, str, AsyncClient], Coroutine[Any, Any, None]],
    ranges: list[V1PieceRange] | list[V2PieceRange],
    url: str,
    infohash: str,
    client: AsyncClient,
) -> WebseedValidationResult:
    """
    Wrapping caller that creates an asyncio task group and creates a validation result.

    Rather than returning, we raise exceptions in the passed validation fn so that we
    cancel execution of the rest of the task group in the case of an error.

    If the inner function does not raise, we assume the range is valid.
    """
    error_type = None
    message = None
    valid = False
    try:
        async with asyncio.TaskGroup() as group:
            _ = [group.create_task(fn(r, url, client)) for r in ranges]
        # after all of them complete...
        valid = True
    except ExceptionGroup as eg:
        # only react to the first exception, they are typically all the same
        e = eg.exceptions[0]
        if isinstance(e, WebseedValidationError):
            error_type = "validation"
            message = str(e)
        elif isinstance(e, WebseedHTTPError):
            error_type = "http"
            message = f"{e.status_code} - {e.detail}"
        elif isinstance(e, TimeoutException | ReadTimeout):
            error_type = "timeout"
        else:
            raise

    return WebseedValidationResult(
        infohash=infohash,
        url=url,
        valid=valid,
        error_type=error_type,
        message=message,
        ranges=ranges,
    )


async def _validate_range_v1(piece_range: V1PieceRange, url: str, client: AsyncClient) -> None:
    chunks = []
    for subrange in piece_range.ranges:
        if subrange.is_padfile:
            chunks.append(bytes(subrange.range_end - subrange.range_start))
        else:
            chunks.append(await _request_range(subrange, subrange.webseed_url(url), client))

    valid = piece_range.validate_data(chunks)
    if not valid:
        raise WebseedValidationError(f"webseed url {url} is invalid for range {piece_range}")


async def _validate_range_v2(piece_range: V2PieceRange, url: str, client: AsyncClient) -> None:
    data = await _request_range(piece_range, piece_range.webseed_url(url), client)
    blocks = [data[i : i + BLOCK_SIZE] for i in range(0, len(data), BLOCK_SIZE)]
    valid = piece_range.validate_data(blocks)
    if not valid:
        raise WebseedValidationError(f"webseed url {url} is invalid for range {piece_range}")


async def _request_range(
    piece_range: FileItemRange | V2PieceRange,
    get_url: str,
    client: AsyncClient,
    retries: dict[int, int] | None = None,
) -> bytes:
    cfg = get_config()

    logger = init_logger("services.webseed_validation")
    logger.debug("%s - retries: %s", get_url, retries)
    if retries is None:
        retries = cfg.services.webseed_validation.retries.copy()

    # range requests are end-inclusive, unlike python
    # so to request the first 1024 bytes, one would request 0-1023,
    # where in python we would index that as [0:1024]
    # see: https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/Range_requests#single_part_ranges
    headers = {
        "Range": f"bytes={piece_range.range_start}-{piece_range.range_end-1}",
    }

    body = b""

    # iterate through the stream and quit early if we transfer more bytes than expected
    expected_size = piece_range.range_end - piece_range.range_start
    async with client.stream(
        "GET", get_url, headers=headers, timeout=cfg.services.webseed_validation.get_timeout
    ) as res:
        async for chunk in res.aiter_bytes():
            body += chunk
            if res.num_bytes_downloaded >= expected_size * 1.1:
                # just break, this is only expected in the case
                # the server doesn't support range requests
                logger.debug("Breaking download, got more bytes than expected from range")
                await res.aclose()

    logger.debug("Downloaded %s bytes from %s", len(body), get_url)

    if len(body) > expected_size:
        logger.debug(
            "Expected %s bytes from %s, got %s - trimming", expected_size, get_url, len(body)
        )
        body = body[:expected_size]

    if retries.get(res.status_code, 0) > 0:
        retries[res.status_code] -= 1
        delay = cfg.services.webseed_validation.retry_delay
        logger.debug(
            "%s - Retrying webseed validation for %s in %s seconds - %s retries remaining",
            res.status_code,
            get_url,
            delay,
            retries[res.status_code],
        )
        await asyncio.sleep(delay)
        return await _request_range(piece_range, get_url, client, retries)

    if res.status_code != 206:
        if res.status_code == 200:
            message = "Server does not support HTTP range requests"
        else:
            message = str(res.status_code)
        raise WebseedHTTPError(status_code=res.status_code, detail=message)

    return body


def _pick_v2_ranges(torrent: Torrent, n_pieces: int) -> list[V2PieceRange]:
    piece_tuples = []
    for path, file_item in torrent.flat_files.items():
        if file_item["pieces root"] not in torrent.piece_layers:
            piece_tuples.append((path, 0))
        else:
            piece_tuples.extend(
                [(path, idx) for idx in range(len(torrent.piece_layers[file_item["pieces root"]]))]
            )

    piece_indices: list[tuple[str, int]] = random.sample(
        piece_tuples, min(n_pieces, len(piece_tuples))
    )
    ranges = [torrent.v2_piece_range(idx[0], idx[1]) for idx in piece_indices]

    return ranges


def _get_client() -> AsyncClient:
    cfg = get_config()
    return AsyncClient(
        limits=Limits(max_connections=cfg.services.webseed_validation.max_connections),
        headers={"User-Agent": cfg.server.user_agent},
        follow_redirects=True,
    )
