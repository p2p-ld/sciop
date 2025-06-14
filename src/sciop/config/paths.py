from pathlib import Path
from typing import Literal

from platformdirs import PlatformDirs
from pydantic import BaseModel, Field, field_validator

_default_userdir = Path().home() / ".config" / "mio"
_dirs = PlatformDirs("sciop", "sciop")
DEFAULT_DB_PATHS = {
    "dev": "db.dev.sqlite",
    "test": "db.test.sqlite",
    "prod": "db.sqlite",
}


class PathConfig(BaseModel):
    """
    All paths used by sciop :)

    Prefer putting paths here rather than in the models where the paths are used,
    but do describe any relation between paths and other config values.
    """

    db: Path | Literal["memory"] = DEFAULT_DB_PATHS["dev"]
    """
    Defaults:

    - `prod`: db.sqlite
    - `dev`: db.dev.sqlite
    - `test`: db.test.sqlite

    if "memory", use an in-memory sqlite database
    """
    logs: Path = Field(
        default=_dirs.user_log_dir,
        description="""
    Directory where logs are stored.
    """,
    )
    template_override: Path | None = None
    """
    If set, directory of template overrides.
    Sciop will use any template within this directory rather than its own
    builtin templates, if present.

    E.g. if a ``template_dir`` contains ``pages/datasets.html`` ,
    that template will be used rather than ``sciop/templates/pages/datasets.html``
    """
    torrents: Path = Path(_dirs.user_data_dir) / "torrents"
    """Directory to store uploaded torrents"""
    docs: Path = Path(_dirs.user_data_dir) / "docs"
    """Directory to store generated docs, if the docs service is enabled"""

    @property
    def sqlite(self) -> str:
        """the path to the sqlite database with the sqlite:// prefix"""
        if self.db == "memory":
            return "sqlite://"
        else:
            return f"sqlite:///{str(self.db.resolve())}"

    @field_validator("torrents", "logs", "docs", mode="after")
    def create_dir(cls, value: Path) -> Path:
        """Ensure directories exist"""
        value.mkdir(parents=True, exist_ok=True)
        return value

    @field_validator("db", mode="after")
    def create_parent_dir(cls, value: Path) -> Path:
        """Ensure parent directory exists"""
        if value is not None and value != "memory":
            value.parent.mkdir(exist_ok=True, parents=True)
        return value
