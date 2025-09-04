from sciop import scheduler, services
from sciop.config import get_config


@scheduler.interval(
    minutes=get_config().services.tracker_scraping.job_interval,
    enabled=get_config().services.tracker_scraping.enabled,
)
async def scrape_torrent_stats() -> None:
    await services.scrape_torrent_stats()


@scheduler.interval(
    minutes=get_config().services.update_feeds.interval,
    enabled=bool(
        get_config().services.update_feeds.enabled and get_config().services.update_feeds.feeds
    ),
)
async def update_atom_feeds() -> None:
    """
    Update any configured atom feeds.

    Atom feeds can be subscribed to and displayed on the homepage for instance news and updates.

    Multiple feeds can be configured for different types of updates,
    or updates from different sources,
    however since the titles and summaries from the feeds are displayed without sanitization,
    feeds outside the instance's control should *never* be configured.
    """
    await services.update_feeds()


@scheduler.interval(
    minutes=get_config().services.site_stats.job_interval,
    enabled=get_config().services.site_stats.enabled,
)
def update_site_stats() -> None:
    services.update_site_stats()


@scheduler.queue(
    enabled=get_config().services.webseed_validation.enabled,
    max_concurrent=get_config().services.webseed_validation.max_concurrent,
)
async def validate_webseed(infohash: str, url: str) -> None:
    await services.validate_webseed_service(infohash, url)
