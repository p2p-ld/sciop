import datetime
from functools import cached_property
from pathlib import Path
from typing import Literal, Optional, Self

from platformdirs import PlatformDirs
from pydantic import (
    BaseModel,
    EmailStr,
    Field,
    SecretStr,
    computed_field,
    field_validator,
    model_validator,
)
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)

from sciop.types import DeltaMinutes

_default_userdir = Path().home() / ".config" / "mio"
_dirs = PlatformDirs("sciop", "sciop")
LOG_LEVELS = Literal["DEBUG", "INFO", "WARNING", "ERROR"]

DEFAULT_DB_LOCATIONS = {
    "dev": "db.dev.sqlite",
    "test": "db.test.sqlite",
    "prod": "db.sqlite",
}


class InstanceRule(BaseModel):
    title: str
    description: str


class InstanceConfig(BaseModel):
    """
    Configuration for the public-facing parts of this instance
    """

    contact_email: Optional[EmailStr] = Field(
        default=None, description="Email to list as contact in page footer"
    )
    rules: list[InstanceRule] = Field(
        default_factory=list, description="Site rules to display in the docs"
    )
    footer: str = Field(
        "",
        description="Footer message shown on the bottom-right of every page."
        "Markdown is supported.",
    )

    @property
    def contact_email_obfuscated(self) -> str | None:
        """Email address like `user [at] domain (dot) tld"""
        if self.contact_email is None:
            return None
        user, domain = self.contact_email.split("@")
        domain, tld = domain.rsplit(".", 1)
        return f"{user} [at] {domain} (dot) {tld}"

    @cached_property
    def footer_html(self) -> str:
        from sciop.services.markdown import render_markdown

        return render_markdown(self.footer)


class LogConfig(BaseModel):
    """
    Configuration for logging
    """

    level: LOG_LEVELS = Field(
        default="INFO",
        description="""
    Severity of log messages to process.
    """,
    )
    level_file: Optional[LOG_LEVELS] = Field(
        default=None,
        description="""
    Severity for file-based logging. If unset, use ``level``
    """,
    )
    level_stdout: Optional[LOG_LEVELS] = Field(
        default=None,
        description="""
    Severity for stream-based logging. If unset, use ``level``
    """,
    )
    dir: Path = Field(
        default=_dirs.user_log_dir,
        description="""
    Directory where logs are stored.
    """,
    )
    file_n: int = Field(
        default=5,
        description="""
    Number of log files to rotate through
    """,
    )
    file_size: int = Field(
        default=2**22,
        description="""
    Maximum size of log files (bytes)
    """,
    )

    @field_validator("level", "level_file", "level_stdout", mode="before")
    @classmethod
    def uppercase_levels(cls, value: Optional[str] = None) -> Optional[str]:
        """
        Ensure log level strings are uppercased
        """
        if value is not None:
            value = value.upper()
        return value

    @field_validator("dir", mode="after")
    def create_dir(cls, value: Path) -> Path:
        value.mkdir(parents=True, exist_ok=True)
        return value


class CSPConfig(BaseModel):
    """
    Configure CSP headers used by the csp_headers middleware

    For now these are single-valued params, expand the annotations as needed.
    """

    default_src: Literal["self"] | str = "self"
    child_src: Literal["self"] | str = "self"
    img_src: Literal["self"] | str = "'self' data:"
    object_src: Literal["none"] | str = "none"
    script_src: Literal["self"] | str = "strict-dynamic"  # "strict-dynamic"
    style_src: Literal["self"] | str = "self"
    font_src: Literal["self"] | str = "self"

    nonce_entropy: int = 90
    enable_nonce: list[str] = Field(default_factory=lambda: ["script_src"])

    def format(self, nonce: str) -> str:
        """
        Create a Content-Security_Policy header string

        TODO: This seems rly slow on every page load, profile this later.
        """

        format_parts = []
        for key, val in self.model_dump().items():
            if key in ("nonce_entropy", "enable_nonce"):
                continue

            # if we're given a pre-quoted string, or multiple params, assume they're quoted already
            if "'" not in val:
                val = f"'{val}'"

            if key in self.enable_nonce:
                val = f"'nonce-{nonce}' {val}"

            key = key.replace("_", "-")
            format_parts.append(f"{key} {val}")

        return "; ".join(format_parts)


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


class Config(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="sciop_",
        env_nested_delimiter="__",
        extra="ignore",
        nested_model_default_partial_update=True,
        yaml_file="sciop.yaml",
    )

    base_url: str = "http://localhost:8000"
    """Root URL where the site is hosted"""
    secret_key: SecretStr
    """Secret key to use when generating auth tokens"""
    db: Optional[Path]
    """
    Defaults:
    
    - `prod`: db.sqlite
    - `dev`: db.dev.sqlite
    - `test`: db.test.sqlite
    
    Optional, if explicitly set to ``None`` , use the in-memory sqlite DB
    """
    db_echo: bool = False
    """Echo all queries made to the database"""
    request_timing: bool = True
    """Enable timing requests, and logging request time"""
    db_pool_size: int = 10
    """Number of active database connections to maintain"""
    db_overflow_size: int = 20
    """Additional database connections that are not allowed to sleep"""
    logs: LogConfig = LogConfig()
    """Log configuration"""
    host: str = "localhost"
    """Host portion of url"""
    port: int = 8000
    """Port where local service should serve from"""
    env: Literal["dev", "prod", "test"]
    """
    dev: interactive, live reloading development mode with dummy data
    test: when running pytest
    prod: when service a live sciop instance
    """
    public_url: str = "http://localhost"
    token_expire_minutes: int = 60 * 24  # AKA 1 day
    """Login authorization token expiration time in minutes"""
    api_prefix: str = "/api/v1"
    """
    Prefix for all JSON API endpoints.
    Placeholder to allow for versioned API in the future
    """
    upload_limit: int = 100 * (2**20)
    """Maximum size of an uploaded file before it is discarded, in bytes"""
    torrent_dir: Path = Path(_dirs.user_data_dir) / "torrents"
    """Directory to store uploaded torrents"""
    enable_versions: bool = True
    """Keep version histories of editable objects"""
    csp: CSPConfig = CSPConfig()
    """Submodel containing CSP config"""
    root_user: str = "root"
    """Default root user created on first run."""
    root_password: Optional[SecretStr] = "rootroot1234"
    """
    Default root password for root user created on first run.
    
    When `env==prod`, this password *must* be supplied on first run explicitly
    via an environment variable (`SCIOP_ROOT_PASSWORD`) or via the .env file.
    This password must *not* be equal to the default.
    
    After the account is created,
    this value can be removed from the environment variables and .env files.
    
    This value is set to `None` by `db.ensure_root` when the program is started normally.    
    """
    rss_feed_cache_delta: DeltaMinutes = datetime.timedelta(minutes=30)
    """The amount of time a cached rss feed entry will be considered valid"""
    rss_feed_cache_clear_time: DeltaMinutes = datetime.timedelta(minutes=10)
    """The amount of time between clearing all the dead keys in the rss feed cache"""
    clear_jobs: bool = False
    """Clear any remaining scheduler jobs on startup"""
    template_dir: Optional[Path] = None
    """
    If set, directory of template overrides.
    Sciop will use any template within this directory rather than its own
    builtin templates, if present.
    
    E.g. if a ``template_dir`` contains ``pages/datasets.html`` ,
    that template will be used rather than ``sciop/templates/pages/datasets.html``
    """
    tracker_scraping: ScrapeConfig = ScrapeConfig()
    """Service config: Tracker scraping"""
    site_stats: StatsConfig = StatsConfig()
    """Service config: Site stats computation"""
    instance: InstanceConfig = InstanceConfig()
    """Configuration for customizing the instance"""

    @computed_field  # type: ignore[prop-decorator]
    @property
    def all_cors_origins(self) -> list[str]:
        return [self.external_url]

    @property
    def external_url(self) -> str:
        """
        Complete url where the site can be reached, including port if local.
        Differentiates between requests that might be made from a local service
        """
        if self.env in ("dev", "test"):
            return f"{self.public_url}:{self.port}"
        elif self.env == "prod":
            return f"{self.public_url}"

    @property
    def sqlite_path(self) -> str:
        if self.db is None:
            return "sqlite://"
        else:
            return f"sqlite:///{str(self.db.resolve())}"

    @property
    def reload(self) -> bool:
        """whether to reload the wsgi server ie. when in dev mode"""
        return self.env == "dev"

    @field_validator("torrent_dir", mode="after")
    def create_dir(cls, value: Path) -> Path:
        """Ensure directories exist"""
        value.mkdir(parents=True, exist_ok=True)
        return value

    @field_validator("db", mode="after")
    def create_parent_dir(cls, value: Path) -> Path:
        """Ensure parent directory exists"""
        if value is not None:
            value.parent.mkdir(exist_ok=True, parents=True)
        return value

    @model_validator(mode="before")
    def default_db(cls, value: dict) -> dict:
        """Add a default db path to args, if not present"""
        if "db" not in value and "env" in value:
            value["db"] = DEFAULT_DB_LOCATIONS[value["env"]]
        return value

    @model_validator(mode="before")
    def explicit_base_url_in_prod(cls, value: dict) -> dict:
        """if env is prod, base_url must be set explicitly"""
        if value.get("env", "") == "prod":
            assert (
                "base_url" in value
            ), "A base_url must be explicitly set when running in `prod` mode"
        return value

    @model_validator(mode="after")
    def root_password_not_default_in_prod(self) -> Self:
        """When env == prod, root_password can't be equal to the default"""
        if self.env == "prod":
            assert (
                self.root_password != self.__class__.model_fields["root_password"].default
            ), "root_password cannot be equal to the default in prod, and must be set explicitly"
        return self

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """
        Read from the following sources,
        in order such that later sources in the list override earlier sources

        - `sciop.yaml` (in cwd)
        - `.env` (in cwd)
        - environment variables prefixed with `SCIOP_`
        - arguments passed on config object initialization

        See [pydantic settings docs](https://docs.pydantic.dev/latest/concepts/pydantic_settings/#customise-settings-sources)
        """
        return init_settings, env_settings, dotenv_settings, YamlConfigSettingsSource(settings_cls)

    @classmethod
    def load(cls, path: Path) -> Self:
        """Load a config file from an explicit path"""
        if not path.exists():
            raise FileNotFoundError(f"config file {path} does not exist")

        if path.suffix in (".yaml", ".yml"):
            import yaml

            with open(path) as f:
                cfg = yaml.safe_load(f)
            return Config(**cfg)
        elif path.name == ".env" or path.suffix == ".env":
            return Config(_env_file=path)
        else:
            ValueError("Path must be a .yaml/.yml or .env file")


config = Config()
