from typing import Literal
from urllib.parse import urljoin

from fastapi import APIRouter, HTTPException
from sqlmodel import select
from sqlmodel.sql.expression import Select

from sciop import crud
from sciop.api.deps import SessionDep
from sciop.config import config
from sciop.models import Dataset, TorrentFeed, Upload
from sciop.types import Scarcity, Threat
from sciop.vendor.fastapi_rss.rss_response import RSSResponse

rss_router = APIRouter(prefix="/rss")

MAX_FEED_ITEMS = 500
"""TODO: make configurable"""
SIZE_BREAKPOINTS = {
    "1gb": ("1GiB", 2**30),
    "10gb": ("10GiB", 10 * (2**30)),
    "100gb": ("100GiB", 100 * (2**30)),
    "500gb": ("500GiB", 500 * (2**30)),
    "1tb": ("1TiB", 2**40),
    "5tb": ("5TiB", 5 * (2**40)),
}
_BREAKPOINTS_TYPE = Literal["1gb", "10gb", "100gb", "500gb", "1tb", "5tb"]
"""
For the benefit of the type checker and docs, try to keep this in sync w/ breakpoints
"""


@rss_router.get("/all.rss")
async def all_feed(session: SessionDep) -> RSSResponse:
    stmt = (
        select(Upload)
        .filter(Upload.is_visible == True)
        .order_by(Upload.created_at.desc())
        .limit(500)
    )
    uploads = session.exec(stmt).all()
    feed = TorrentFeed.from_uploads(
        title="Sciop: All",
        description="All recent uploads",
        link=urljoin(f"{config.base_url}", "/all.rss"),
        uploads=uploads,
    )
    return RSSResponse(feed)


def _size_stmt(size: int, direction: Literal["lt", "gt"]) -> Select:
    if direction == "lt":
        stmt = (
            select(Upload)
            .filter(
                Upload.is_visible == True,
                Upload.size <= size,
            )
            .order_by(Upload.created_at.desc())
            .limit(MAX_FEED_ITEMS)
        )
    elif direction == "gt":
        stmt = (
            select(Upload)
            .filter(
                Upload.is_visible == True,
                Upload.size >= size,
            )
            .order_by(Upload.created_at.desc())
            .limit(MAX_FEED_ITEMS)
        )
    else:
        raise ValueError(f"Unknown direction: {direction}")
    return stmt


@rss_router.get("/size/lt/{size}.rss")
async def size_lt(size: _BREAKPOINTS_TYPE, session: SessionDep) -> RSSResponse:
    """
    Feed of items smaller than the given size.

    the size path param must be one of `SIZE_BREAKPOINTS` .
    This is quantized rather than a free parameter to avoid needing to compute
    every possible size feed.
    """
    if size not in SIZE_BREAKPOINTS:
        raise HTTPException(404, f"Unknown size, must be one of {set(SIZE_BREAKPOINTS.keys())}")
    size_title, size_int = SIZE_BREAKPOINTS[size]

    stmt = _size_stmt(size_int, direction="lt")
    uploads = session.exec(stmt).all()
    feed = TorrentFeed.from_uploads(
        title=f"Sciop: <{size_title}",
        description=f"All uploads less than {size_title}",
        link=urljoin(f"{config.base_url}", f"/size/lt/{size}.rss"),
        uploads=uploads,
    )
    return RSSResponse(feed)


@rss_router.get("/size/gt/{size}.rss")
async def size_gt(size: _BREAKPOINTS_TYPE, session: SessionDep) -> RSSResponse:
    """
    Feed of items larger than the given size.

    the size path param must be one of `SIZE_BREAKPOINTS` .
    This is quantized rather than a free parameter to avoid needing to compute
    every possible size feed.
    """
    if size not in SIZE_BREAKPOINTS:
        raise HTTPException(404, f"Unknown size, must be one of {set(SIZE_BREAKPOINTS.keys())}")
    size_title, size_int = SIZE_BREAKPOINTS[size]

    stmt = _size_stmt(size_int, direction="gt")
    uploads = session.exec(stmt).all()
    feed = TorrentFeed.from_uploads(
        title=f"Sciop: >{size_title}",
        description=f"All uploads larger than {size_title}",
        link=urljoin(f"{config.base_url}", f"/size/gt/{size}.rss"),
        uploads=uploads,
    )
    return RSSResponse(feed)


@rss_router.get("/seeds/1-10.rss")
async def low_seeders(session: SessionDep) -> RSSResponse:
    stmt = (
        select(Upload)
        .filter(
            Upload.is_visible == True,
            Upload.seeders > 0,
            Upload.seeders <= 10,
        )
        .order_by(Upload.created_at.desc())
        .limit(500)
    )
    uploads = session.exec(stmt).all()
    feed = TorrentFeed.from_uploads(
        title="Sciop: Seeds Needed",
        description="Uploads with at least one, but less than 10 seeders",
        link=urljoin(f"{config.base_url}", "/seeds/1-10.rss"),
        uploads=uploads,
    )
    return RSSResponse(feed)


@rss_router.get("/seeds/unseeded.rss")
async def unseeded(session: SessionDep) -> RSSResponse:
    stmt = (
        select(Upload)
        .filter(
            Upload.is_visible == True,
            Upload.seeders == 0,
        )
        .order_by(Upload.created_at.desc())
        .limit(500)
    )
    uploads = session.exec(stmt).all()
    feed = TorrentFeed.from_uploads(
        title="Sciop: Reseeds Needed",
        description="Torrents with no current seeds",
        link=urljoin(f"{config.base_url}", "/seeds/unseeded.rss"),
        uploads=uploads,
    )
    return RSSResponse(feed)


@rss_router.get("/tag/{tag}.rss")
async def tag_feed(tag: str, session: SessionDep) -> RSSResponse:
    uploads = crud.get_uploads_from_tag(session=session, tag=tag, visible=True)
    if not uploads:
        raise HTTPException(404, detail=f"No uploads found for tag {tag}")
    feed = TorrentFeed.from_uploads(
        title=f"Sciop tag: {tag}",
        description=f"A feed of public data torrents tagged with {tag}",
        link=urljoin(f"{config.base_url}", f"/tag/{tag}.rss"),
        uploads=uploads,
    )
    return RSSResponse(feed)


@rss_router.get("/source/{availability}.rss")
async def source_feed(availability: str, session: SessionDep) -> RSSResponse:
    if availability == "available":
        stmt = (
            select(Upload)
            .join(Dataset)
            .filter(Upload.is_visible == True, Dataset.source_available == True)
            .order_by(Upload.created_at.desc())
            .limit(MAX_FEED_ITEMS)
        )
    elif availability == "unavailable":
        stmt = (
            select(Upload)
            .join(Dataset)
            .filter(Upload.is_visible == True, Dataset.source_available == False)
            .order_by(Upload.created_at.desc())
            .limit(MAX_FEED_ITEMS)
        )
    else:
        raise HTTPException(404, detail=f"No such source availability as {availability}")
    uploads = session.exec(stmt).all()
    feed = TorrentFeed.from_uploads(
        title=f"Sciop availability: {availability}",
        description=f"A feed of public data torrents which are {availability} at their source",
        link=urljoin(f"{config.base_url}", f"/source/{availability}.rss"),
        uploads=uploads,
    )
    return RSSResponse(feed)


@rss_router.get("/scarcity/{scarcity}.rss")
async def scarcity_feed(scarcity: str, session: SessionDep) -> RSSResponse:
    if scarcity not in Scarcity:
        raise HTTPException(404, detail=f"Scarcity {scarcity} does not exist")
    stmt = (
        select(Upload)
        .join(Dataset)
        .filter(Upload.is_visible == True, Dataset.scarcity == scarcity)
        .order_by(Upload.created_at.desc())
        .limit(MAX_FEED_ITEMS)
    )
    uploads = session.exec(stmt).all()
    feed = TorrentFeed.from_uploads(
        title=f"Sciop scarcity: {scarcity}",
        description=f"A feed of public data torrents which have scarcity level {scarcity}",
        link=urljoin(f"{config.base_url}", f"/source/{scarcity}.rss"),
        uploads=uploads,
    )
    return RSSResponse(feed)


@rss_router.get("/threat/{threat}.rss")
async def threat_feed(threat: str, session: SessionDep) -> RSSResponse:
    if threat not in Threat:
        raise HTTPException(404, detail=f"Threat {threat} does not exist")
    stmt = (
        select(Upload)
        .join(Dataset)
        .filter(Upload.is_visible == True, Dataset.threat == threat)
        .order_by(Upload.created_at.desc())
        .limit(MAX_FEED_ITEMS)
    )
    uploads = session.exec(stmt).all()
    feed = TorrentFeed.from_uploads(
        title=f"Sciop threat: {threat}",
        description=f"A feed of public data torrents which have threat level {threat}",
        link=urljoin(f"{config.base_url}", f"/source/{threat}.rss"),
        uploads=uploads,
    )
    return RSSResponse(feed)
