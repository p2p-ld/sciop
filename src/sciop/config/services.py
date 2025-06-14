from pydantic import BaseModel, Field


class JobConfig(BaseModel):
    """Abstract shared class for job configs"""

    enabled: bool = True


class ScrapeErrorBackoffs(BaseModel):
    """Backoff multiplier for each type of scraping error"""

    default: float = 1
    unpack: float = 1
    timeout: float = 2
    connection: float = 5
    dns: float = 10


class ScrapeConfig(JobConfig):
    """Configure scraping stats from other trackers"""

    interval: int = 30
    """Frequency of tracker scraping, in minutes - 
    how frequently a given tracker/torrent pair should be scraped"""
    job_interval: int = 10
    """Frequency of executing the scrape job, in minutes - 
    only scrapes torrents that haven't been scraped in more than `interval` minutes."""
    n_workers: int = Field(default=24, description="""Number of trackers to scrape in parallel""")
    connection_timeout: int = Field(
        default=10,
        description="""
    Timeout for initializing UDP requests, in seconds
    """,
    )
    scrape_timeout: int = Field(
        default=30,
        description="""
    Timeout for scrape responses, in seconds
    """,
    )
    backoff: ScrapeErrorBackoffs = ScrapeErrorBackoffs()
    """
    Exponential penalties for different kinds of tracker errors,
    computed like:
    
    interval * backoff_multiplier * 2^{n_errors}
    """
    max_backoff: float = 60 * 24 * 30
    """
    Maximum time that a tracker can be backed off, in minutes
    Default: 30 days (yes, in minutes)
    """
    http_tracker_single_only: list[str] = Field(default_factory=list)
    """
    Announce URLs of HTTP trackers that are known to only respond to single infohash at a time
    in their scrape responses.
    It can be very expensive to scrape these trackers,
    so we only try and scrape from them if they are special trackers we
    really want peer information from.
    """
    http_tracker_scrape_all: list[str] = Field(default_factory=list)
    """
    Announce URLs of HTTP trackers that are known to only allow scraping *all*
    torrents from a request to a `scrape` URL, rather than a subset specified by infohash.
    
    E.g. academictorrents: https://github.com/academictorrents/academictorrents-docs/issues/44#issuecomment-2799762080
    """


class StatsConfig(JobConfig):
    """Computation of site statistics"""

    job_interval: int = Field(
        default=60, description="""frequency of recalculating stats, in minutes"""
    )


class DocsConfig(JobConfig):
    """
    Service for auto-building docs on startup in `dev` mode.

    Sciop must be installed with the optional `[docs]` dependency group.

    See also [PathConfig.docs][sciop.config.paths.PathConfig.docs]
    for configuring where docs are built to and served from.
    """

    watch: bool = True
    """
    Whether docs should be added to the list of watched directories
    so they are rebuilt on changes 
    """
    dirty: bool = True
    """
    Build docs in "dirty" mode, only rebuilding what is stale,
    or force a full rebuild if `False`
    """


class ServicesConfig(BaseModel):
    """
    Top-level config for all background services
    """

    clear_jobs: bool = False
    """Clear any remaining scheduler jobs on startup"""
    tracker_scraping: ScrapeConfig = ScrapeConfig()
    """Service config: Tracker scraping"""
    site_stats: StatsConfig = StatsConfig()
    """Service config: Site stats computation"""
    docs: DocsConfig = DocsConfig()
    """Live-building docs in dev mode"""
