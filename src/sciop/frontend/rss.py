from urllib.parse import urljoin

from fastapi import APIRouter, HTTPException
from sqlmodel import select

from sciop import crud
from sciop.api.deps import SessionDep
from sciop.config import config
from sciop.models import Dataset, TorrentFeed, Upload
from sciop.types import Scarcity, Threat
from sciop.vendor.fastapi_rss.rss_response import RSSResponse

rss_router = APIRouter(prefix="/rss")

MAX_FEED_ITEMS = 500
"""TODO: make configurable"""


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
