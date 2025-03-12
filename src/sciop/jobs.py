from sciop import scheduler, services
from sciop.config import config


@scheduler.interval(
    minutes=config.tracker_scraping.interval, enabled=config.tracker_scraping.enabled
)
def scrape_torrent_stats() -> None:
    services.scrape_torrent_stats()
