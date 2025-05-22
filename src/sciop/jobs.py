from sciop import scheduler, services
from sciop.config import config


@scheduler.interval(
    minutes=config.services.tracker_scraping.job_interval,
    enabled=config.services.tracker_scraping.enabled,
)
async def scrape_torrent_stats() -> None:
    await services.scrape_torrent_stats()


@scheduler.interval(
    minutes=config.services.site_stats.job_interval, enabled=config.services.site_stats.enabled
)
async def update_site_stats() -> None:
    await services.update_site_stats()
