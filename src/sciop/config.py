from pathlib import Path
from typing import Literal, Optional, Self

from platformdirs import PlatformDirs
from pydantic import BaseModel, Field, computed_field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_default_userdir = Path().home() / ".config" / "mio"
_dirs = PlatformDirs("sciop", "sciop")
LOG_LEVELS = Literal["DEBUG", "INFO", "WARNING", "ERROR"]

DEFAULT_DB_LOCATIONS = {
    "dev": "db.dev.sqlite",
    "test": "db.test.sqlite",
    "prod": "db.sqlite",
}


class LogConfig(BaseModel):
    """
    Configuration for logging
    """

    level: LOG_LEVELS = "INFO"
    """
    Severity of log messages to process.
    """
    level_file: Optional[LOG_LEVELS] = None
    """
    Severity for file-based logging. If unset, use ``level``
    """
    level_stdout: Optional[LOG_LEVELS] = None
    """
    Severity for stream-based logging. If unset, use ``level``
    """
    dir: Path = _dirs.user_log_dir
    """
    Directory where logs are stored.
    """
    file_n: int = 5
    """
    Number of log files to rotate through
    """
    file_size: int = 2**22  # roughly 4MB
    """
    Maximum size of log files (bytes)
    """

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


class Config(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="sciop_",
        env_nested_delimiter="__",
        extra="ignore",
        nested_model_default_partial_update=True,
    )

    base_url: str = "http://localhost:8000"
    """Root URL where the site is hosted"""
    secret_key: str
    db: Optional[Path]
    """
    Defaults:
    - `prod`: db.sqlite
    - `dev`: db.dev.sqlite
    - `test`: db.test.sqlite
    
    Optional, if explicitly set to ``None`` , use the in-memory sqlite DB
    """
    logs: LogConfig = LogConfig()
    host: str = "localhost"
    port: int = 8000
    env: Literal["dev", "prod", "test"]
    public_url: str = "http://localhost"
    token_expire_minutes: int = 30
    api_prefix: str = "/api/v1"
    upload_limit: int = 2**20
    """in bytes"""
    torrent_dir: Path = Path(_dirs.user_data_dir) / "torrents"
    """Directory to store uploaded torrents"""
    csp: CSPConfig = CSPConfig()
    root_user: str = "root"
    """
    Default root user created on first run.
    """
    root_password: Optional[str] = "rootroot1234"
    """
    Default root password for root user created on first run.
    
    When `env==prod`, this password *must* be supplied on first run explicitly
    via an environment variable (`SCIOP_ROOT_PASSWORD`) or via the .env file.
    This password must *not* be equal to the default.
    
    After the account is created,
    this value can be removed from the environment variables and .env files.
    
    This value is set to `None` by `db.ensure_root` when the program is started normally.    
    """

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
        value.parent.mkdir(exist_ok=True, parents=True)
        return value

    @model_validator(mode="before")
    def default_db(cls, value: dict) -> dict:
        """Add a default db path to args, if not present"""
        if "db" not in value and "env" in value:
            value["db"] = DEFAULT_DB_LOCATIONS[value["env"]]
        return value

    @model_validator(mode="after")
    def root_password_not_default_in_prod(self) -> Self:
        """When env == prod, root_password can't be equal to the default"""
        if self.env == "prod":
            assert (
                self.root_password != self.model_fields["root_password"].default
            ), "root_password cannot be equal to the default in prod, and must be set explicitly"
        return self


config = Config()
