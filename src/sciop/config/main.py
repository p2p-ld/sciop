import secrets
import sys
from pathlib import Path
from time import time
from typing import Any, Literal, Optional, Self

from pydantic import (
    Field,
    ModelWrapValidatorHandler,
    PrivateAttr,
    SecretStr,
    ValidationInfo,
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
    if _config is None:
        _config = Config()
    elif reload or _config.should_reload():
        _config = _config.reload()

    return _config


def set_config(config: "Config") -> "Config":
    """
    Set an instantiated config object as the active config that will be returned by `get_config`.

    Setting individual values on a config object is not supported and should not be done.
    """
    global _config
    _config = config
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
        use_enum_values=True,
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
    config_watch_minutes: int = 5
    """
    Minutes to wait between re-checking the mtime of any config sources that were found
    to reload the config. This avoids needing to `stat` source files in the potentially
    thousands of times the config object is accessed per minute.
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

    _yaml_source: Path | None = None
    _source_mtimes: dict[Path, float] = PrivateAttr(default_factory=dict)
    _last_checked: float = time()

    @property
    def reload_uvicorn(self) -> bool:
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

    @model_validator(mode="wrap")
    @classmethod
    def get_source_mtimes(
        cls, data: Any, handler: ModelWrapValidatorHandler[Self], info: ValidationInfo
    ) -> Self:
        """
        Get the mtimes of any source files found

        If the config file was loaded from a yaml file with [.load][sciop.config.main.Config.load],
        use that as the source file to check.

        Otherwise watch a `.env` and/or `sciop.yaml` file in the cwd, if found.
        """

        after = handler(data)
        mtimes = {}
        if (env := Path.cwd() / ".env").exists():
            mtimes[env] = env.stat().st_mtime
        if "_yaml_source" in data:
            after._yaml_source = Path(data["_yaml_source"]).resolve()
        elif (local_yaml := Path.cwd() / "sciop.yaml").exists():
            after._yaml_source = local_yaml

        if after._yaml_source is not None:
            mtimes[after._yaml_source] = after._yaml_source.stat().st_mtime

        after._source_mtimes = mtimes
        return after

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
            cfg["_yaml_source"] = path
            return Config(**cfg)
        elif path.name == ".env" or path.suffix == ".env":
            return Config(_env_file=path)
        else:
            ValueError("Path must be a .yaml/.yml or .env file")

    def should_reload(self) -> bool:
        """
        Whether the config sources have been changed and the config should be reloaded

        Returns `False` if the [config_watch_minutes][.config_watch_minutes] have not elapsed
        since the last check, if the mtimes are unchanged, or no source files were found.

        Returns `True` if the mtimes of the identified source files have changed

        When reloading elsewhere, use `.reload()` rather than re-instantiating the object
        to preserve any explicitly-passed config source paths.
        """
        if not self._source_mtimes:
            return False

        current_time = time()
        if current_time < self._last_checked + (self.config_watch_minutes * 60):
            self._last_checked = current_time
            return False

        try:
            self._last_checked = current_time
            return any(
                source.stat().st_mtime > mtime for source, mtime in self._source_mtimes.items()
            )
        except Exception as e:
            # maybe the OS doesn't support mtimes, we shouldn't crash here
            from sciop.logging import init_logger

            logger = init_logger("config")
            logger.warning(f"Caught error while checking whether should reload config:\n{e}")
            return False

    def reload(self) -> "Config":
        """
        If instantiated from a custom yaml source with `.load`,
        recreate a new `Config` object from that source.

        Otherwise equivalent to instantiating without arguments.
        """
        if (
            self._yaml_source
            and self._yaml_source.resolve() != (Path().cwd() / "sciop.yaml").resolve()
        ):
            new_config = Config.load(self._yaml_source)
        else:
            new_config = Config()
        return new_config


def _lifespan_load_config() -> None:
    """
    Private method to load from a passed config file within the app when started with
    `sciop start -c custom_config`, since uvicorn reloads the whole interpreter
    every time, we have to get a little meta and re-evaluate the cli params.

    If we can't or no custom config was passed, does nothing and allows
    `get_config` to work as normal.
    """
    args = sys.argv
    try:
        # avoid getting any `-c` params potentially passed to the interpreter
        # or otherwise not for us
        start_idx = args.index("start")
    except ValueError:
        # not run via the `start` command
        return

    args = args[start_idx:]
    if "-c" in args:
        flag_idx = args.index("-c")
    elif "--config" in args:
        flag_idx = args.index("--config")
    else:
        return

    config_path = None
    try:
        config_path = args[flag_idx + 1]
        cfg = Config.load(Path(config_path))
        from sciop.logging import init_logger

        logger = init_logger(
            "config",
            log_dir=cfg.paths.logs,
            log_file_n=cfg.logs.file_n,
            log_file_size=cfg.logs.file_size,
            level=cfg.logs.level_stdout if cfg.logs.level_stdout is not None else cfg.logs.level,
            file_level=cfg.logs.level_file if cfg.logs.level_file is not None else cfg.logs.level,
        )
        logger.info(f"Using config from custom path: {config_path}")
        logger.info(Path(config_path).read_text())
        set_config(cfg)
    except Exception as e:

        from sciop.logging import init_logger

        logger = init_logger("config")
        logger.warning(
            f"Detected config passed with -c or --config, but got error when loading. "
            f"Attempting to continue with config loaded from standard locations.\n"
            f"Got config arg: {config_path}\n"
            f"Got error:\n{str(e)}"
        )
        return
