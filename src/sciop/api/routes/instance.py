from fastapi import APIRouter, HTTPException
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlmodel import select

from sciop import crud
from sciop.api.deps import RawSessionDep
from sciop.config import config
from sciop.config.instance import InstanceRule
from sciop.models import SiteStats, SiteStatsRead

instance_router = APIRouter(prefix="/instance")


@instance_router.get("/stats")
async def get_stats(session: RawSessionDep = None) -> Page[SiteStatsRead]:
    """
    Get paginated collection of stats history
    """
    if not config.services.site_stats.enabled:
        raise HTTPException(404, detail="Site stats are not enabled for this instance")
    return paginate(session, select(SiteStats).order_by(SiteStats.created_at.desc()))


@instance_router.get("/stats/latest")
async def get_stats_latest(session: RawSessionDep = None) -> SiteStatsRead:
    """
    Get the latest site stats
    """
    if not config.services.site_stats.enabled:
        raise HTTPException(404, detail="Site stats are not enabled for this instance")
    stats = crud.get_latest_site_stats(session=session)
    if stats is None:
        raise HTTPException(404, detail="Site stats have not been computed")
    return stats


@instance_router.get("/rules")
async def get_rules() -> list[InstanceRule]:
    """
    Get the rules for the instance
    """
    return config.instance.rules
