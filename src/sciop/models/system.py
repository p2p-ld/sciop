from typing import Optional, Self

from pydantic import Field, field_validator, model_validator

from sciop.config import config
from sciop.models.mixins import TemplateModel


class NginxConfig(TemplateModel):
    __template__ = "system/nginx.conf.j2"

    host: str = Field(
        default=config.host,
        description="The hostname that sciop will be hosted at, e.g. `sciop.net`",
    )
    port: int = Field(
        default=config.port,
        description="The localhost port that sciop will be hosted at",
    )
    max_upload_size: str = Field(
        default="16M",
        description="The maximum allowed body size for client requests "
        "as an nginx size string like `1M`",
    )
    cache_enable: bool = Field(default=True, description="Enable caching of static pages")
    cache_files: int = Field(default=300, description="Number of files to cache")
    cache_size: str = Field(
        default="200m", description="Size of cache in memory before entrie are removed"
    )
    cache_keys_size: str = Field(
        default="10m", description="Size of memory used on mapping cache keys to values"
    )
    cache_duration: str = Field(default="30m", description="Duration of cache for static files")
    ratelimit_enable: bool = Field(
        default=False,
        description="Enable rate limiting, configured in other options. "
        "For help on all ratelimit params, "
        "see: https://blog.nginx.org/blog/rate-limiting-nginx",
    )
    ratelimit_name: Optional[str] = Field(
        default="sciopRatelimitZone", description="Name to give the generated rate limit"
    )
    ratelimit_period: Optional[str] = Field(
        default=None,
        description="The period over which to consider ratelimits, "
        "expressed as an nginx time string like '5s' or '1h'. "
        "Required if ratelimit_enable=True",
    )
    ratelimit_rate: Optional[str] = Field(
        default=None,
        description="Maximum rate limit for requests, defined as nginx request limit string "
        "like `10r/s`."
        "Required if ratelimit_enable=True",
    )
    ratelimit_burst: Optional[int] = Field(
        default=1, description="How many requests to queue, rather than reject in a burst. "
    )
    ratelimit_delay: Optional[int | str] = Field(
        default=0,
        description="Number of requests after which to apply the rate limit. "
        "0 is considered `nolimit`",
    )

    @model_validator(mode="after")
    def ensure_ratelimits_set(cls, value: Self) -> Self:
        if value.ratelimit_enable:
            for field in value.__class__.model_fields:
                if not field.startswith("ratelimit"):
                    continue
                assert (
                    getattr(value, field) is not None
                ), f"All ratelimit params must be set if ratelimit_enable=True. Missing {field}"
        return value

    @field_validator("ratelimit_delay", mode="after")
    @classmethod
    def delay_0_is_nodelay(cls, val: int) -> int | str:
        if val == 0:
            return "nodelay"
        return val
