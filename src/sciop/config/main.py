import secrets
from pathlib import Path
from typing import Literal, Optional, Self

from pydantic import (
    Field,
    SecretStr,
    model_validator,
)
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)

from sciop.config.db import DBConfig
from sciop.config.feeds import FeedConfig
from sciop.config.instance import InstanceConfig
from sciop.config.logs import LogConfig
from sciop.config.paths import DEFAULT_DB_PATHS, PathConfig
from sciop.config.server import ServerConfig
from sciop.config.services import ServicesConfig

_config: "Config" = None


def get_config(reload: bool = False) -> "Config":
    """
    Get the global singleton config, loading it if it's not already created.

    Args:
        reload (bool): If ``True``, reload the config from default sources.
    """
    global _config
    if _config is None or reload:
        _config = Config()
    return _config


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
    env: Literal["dev", "prod", "test"] = "dev"
    """
    dev: interactive, live reloading development mode with dummy data
    test: when running pytest
    prod: when service a live sciop instance
    
    `dev` and `test` modes should *never* be made publicly accessible,
    and should *always* be assumed to be temporary and local.
    """
    secret_key: SecretStr = Field(default_factory=lambda: secrets.token_hex(32), min_length=64)
    """
    Secret key to use when generating auth tokens
    
    When not explicitly specified, 
    a new secret key will be generated every time Config is instantiated.
    This will mean that all existing authentication cookies will no longer be valid
    and everyone will need to login. 
    At the moment, this is more of an annoyance than anything,
    but in the future when the secret key will be used to sign instance events,
    leaving this unset will likely break everything.
    
    You should generate and explicitly set a secret_key,
    either using the sciop cli: `sciop config copy` 
    or openssl: `openssl rand -hex 32`
    """
    token_expire_minutes: int = 60 * 24  # AKA 1 day
    """Login authorization token expiration time in minutes"""
    api_prefix: str = "/api/v1"
    """
    Prefix for all JSON API endpoints.
    Placeholder to allow for versioned API in the future
    """
    enable_versions: bool = True
    """Keep version histories of editable objects"""
    upload_limit: int = 100 * (2**20)
    """Maximum size of an uploaded file before it is discarded, in bytes"""
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

    # --------------------------------------------------
    # Configuration sub-models
    # --------------------------------------------------
    db: DBConfig = DBConfig()
    """Detailed database configuration"""
    feeds: FeedConfig = FeedConfig()
    """Configuration for RSS feeds and caching"""
    instance: InstanceConfig = InstanceConfig()
    """Configuration for customizing user-facing parts of the instance"""
    logs: LogConfig = LogConfig()
    """Logging, levels, formatting, etc."""
    paths: PathConfig = PathConfig()
    """All the paths used by sciop"""
    server: ServerConfig = ServerConfig()
    """Configuration of the server backend - how and from where content is served"""
    services: ServicesConfig = ServicesConfig()
    """Configuration for all background tasks and services"""

    @property
    def reload(self) -> bool:
        """whether to reload the wsgi server ie. when in dev mode"""
        return self.env == "dev"

    @model_validator(mode="before")
    def default_db(cls, value: dict) -> dict:
        """Add a default db path to args, if not present"""
        if "db" not in value.get("paths", {}):
            if "paths" not in value:
                value["paths"] = {}
            value["paths"]["db"] = DEFAULT_DB_PATHS[value.get("env", "dev")]
        return value

    @model_validator(mode="before")
    def explicit_base_url_in_prod(cls, value: dict) -> dict:
        """if env is prod, base_url must be set explicitly"""
        if value.get("env", "") == "prod":
            assert "server" in value, "Must have server config in `prod` mode"
            assert (
                "base_url" in value["server"]
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
