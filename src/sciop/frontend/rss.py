from urllib.parse import urljoin

from fastapi import APIRouter, HTTPException

from sciop import crud
from sciop.api.deps import SessionDep
from sciop.config import config
from sciop.models import TorrentFeed
from sciop.vendor.fastapi_rss.rss_response import RSSResponse

rss_router = APIRouter(prefix="/rss")


@rss_router.get("/tag/{tag}.rss")
async def tag_feed(tag: str, session: SessionDep) -> RSSResponse:
    uploads = crud.get_uploads_from_tag(session=session, tag=tag)
    if not uploads:
        raise HTTPException(404, detail=f"No uploads found for tag {tag}")
    feed = TorrentFeed.from_uploads(
        title=f"Sciop tag: {tag}",
        description=f"A feed of public data torrents tagged with {tag}",
        link=urljoin(f"{config.base_url}", f"/tag/{tag}.rss"),
        uploads=uploads,
    )
    return RSSResponse(feed)
