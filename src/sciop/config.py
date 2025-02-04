from pathlib import Path
from typing import Literal, Optional

from platformdirs import PlatformDirs
from pydantic import (
    BaseModel,
    computed_field,
    field_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict

_default_userdir = Path().home() / ".config" / "mio"
_dirs = PlatformDirs("sciop", "sciop")
LOG_LEVELS = Literal["DEBUG", "INFO", "WARNING", "ERROR"]


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

class Config(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="sciop_",
        env_nested_delimiter="__",
        extra="ignore",
        nested_model_default_partial_update=True,
    )

    secret_key: str
    db: Optional[Path] = Path("./db.sqlite")
    """
    Optional, if set to ``None`` , use the in-memory sqlite DB
    """
    logs: LogConfig = LogConfig()
    host: str = "localhost"
    port: int = 8000
    env: Literal["dev", "prod", "test"] = "dev"
    public_url: str = "http://localhost"
    token_expire_minutes: int = 30
    api_prefix: str = "/api/v1"
    upload_limit: int = 2**20
    """in bytes"""
    torrent_dir: Path = Path(_dirs.user_data_dir) / 'torrents'
    """Directory to store uploaded torrents"""

    @computed_field  # type: ignore[prop-decorator]
    @property
    def all_cors_origins(self) -> list[str]:
        if self.env == "dev":
            return [f"{self.public_url}:{self.port}"]
        elif self.env == "prod":
            return [f"{self.public_url}"]

    @property
    def sqlite_path(self) -> str:
        if self.db is None:
            return "sqlite://"
        else:
            return f"sqlite:///{str(self.db.resolve())}"

    @property
    def reload(self) -> bool:
        """whether to reload the wsgi server ie. when in dev mode"""
        if self.env == "dev":
            return True
        else:
            return False

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




config = Config()
