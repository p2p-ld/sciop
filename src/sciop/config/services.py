from pydantic import BaseModel, ConfigDict, Field


class JobConfig(BaseModel):
    """Abstract shared class for job configs"""

    enabled: bool = True


class QueueJobConfig(JobConfig):
    """Abstract shared class for queued job configs"""

    queue_name: str
    """
    Name of the queue (and thus pool executor) this job runs in
    For now, spawn pools for each kind of job,
    but in the future, allow shared pools for related tasks.
    """
    max_concurrent: int = 1
    """
    Maximum instances of this job that can run in parallel
    """


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


class WebseedValidationConfig(QueueJobConfig):
    """
    Configuration of adding and validatation of webseeds from the web UI.

    If enabled, when webseeds are added, sciop will request `n_pieces` from the torrent
    (or, in the case of large piece sizes, the number of pieces that keeps us
    below `max_validation_data` bytes worth of bandwidth)
    """

    queue_name: str = "webseeds"
    max_concurrent: int = 2
    """
    The size of the process pool that controls the number of added webseeds validated concurrently.
    
    This is a potentially memory-intensive job, so keep default count low.
    """

    enable_adding_webseeds: bool = True
    """
    If ``False`` , don't allow adding webseeds from the web UI or API at all.
    
    If `enable_adding_webseeds` is `True` but `enable` is `False`,
    webseeds can be added but they will not be validated.
    
    If `enable_adding_webseeds` is `False` but `enable` is `True`,
    webseeds cannot be added and will not be validated.
    """
    n_pieces: int = 25
    """
    The number of pieces to validate.
    
    Overridden by max_validation_data - we will validate fewer pieces than `n_pieces`
    to avoid going over our bandwidth budget.
    """
    max_validation_data: int = 1 * (2**30)  # 1 GB
    """
    Maximum amount of data per validation to download, in bytes
    """
    max_connections: int = 20
    """
    Maximum requests active per validation job.
    
    See: https://www.python-httpx.org/advanced/resource-limits/
    """
    retries: dict[int, int] = Field(default_factory=lambda: {429: 5})
    """
    Maximum number of retries for a given HTTP response code.
    
    Default is to retry 5 times for 429's
    """
    retry_delay: int = 15
    """
    Delay between retries, in seconds.
    """
    get_timeout: float = 60
    """
    timeout for get requests when validating
    """

    model_config = ConfigDict(use_enum_values=True)

    def get_max_n_pieces(self, piece_length: int) -> int:
        """
        Maximum pieces that should be validated.

        Actual pieces validated may be lower than this, e.g. in the case the torrent has
        fewer pieces than we want to validate.
        """
        return min(self.n_pieces, self.max_validation_data // piece_length)


class ServicesConfig(BaseModel):
    """
    Top-level config for all background services
    """

    tracker_scraping: ScrapeConfig = ScrapeConfig()
    """Service config: Tracker scraping"""
    site_stats: StatsConfig = StatsConfig()
    """Service config: Site stats computation"""
    docs: DocsConfig = DocsConfig()
    """Live-building docs in dev mode"""
    webseed_validation: WebseedValidationConfig = Field(
        default_factory=lambda: WebseedValidationConfig()
    )
