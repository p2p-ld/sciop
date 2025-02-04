from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from urllib.parse import urljoin

from sciop import crud
from sciop.api.deps import CurrentAccount, SessionDep, RequireReviewer
from sciop.config import config
from sciop.const import TEMPLATE_DIR
from sciop.models import DatasetCreate, Dataset, DatasetInstance, TorrentFeed
from sciop.vendor.fastapi_rss.rss_response import RSSResponse, RSSFeed

rss_router = APIRouter(prefix="/rss")


@rss_router.get("/tag/{tag}.rss")
async def tag_feed(tag: str, session: SessionDep) -> RSSResponse:
    instances = crud.get_instances_from_tag(session=session, tag=tag)
    if not instances:
        raise HTTPException(404, detail=f"No uploads found for tag {tag}")
    feed = TorrentFeed.from_instances(
        title=f"Sciop tag: {tag}",
        description=f"A feed of public data torrents tagged with {tag}",
        link=urljoin(f"{config.base_url}", f"/tag/{tag}.rss"),
        instances=instances,
    )
    return RSSResponse(feed)
