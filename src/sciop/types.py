import re
from enum import StrEnum
from html import escape
from typing import Annotated, Optional, TypeAlias

from annotated_types import Gt, MaxLen
from pydantic import AfterValidator, AnyUrl, Field, TypeAdapter
from slugify import slugify

USERNAME_PATTERN = re.compile(r"^[\w-]+$")

IDField: TypeAlias = Optional[Annotated[int, Gt(0)]]
EscapedStr: TypeAlias = Annotated[str, AfterValidator(escape)]
SlugStr: TypeAlias = Annotated[str, AfterValidator(slugify)]
UsernameStr: TypeAlias = Annotated[
    str, Field(min_length=3, max_length=64, pattern=USERNAME_PATTERN)
]
AnyUrlTypeAdapter = TypeAdapter(AnyUrl)
MaxLenURL = Annotated[
    str, MaxLen(512), AfterValidator(lambda url: str(AnyUrlTypeAdapter.validate_python(url)))
]


class AccessType(StrEnum):
    unknown = "unknown"
    public = "public"
    registration = "registration"
    paywalled = "paywalled"
    proprietary = "proprietary"


class Scarcity(StrEnum):
    unknown = "unknown"
    source_only: Annotated[str, "The dataset is likely to only exist at the canonical source"] = (
        "source_only"
    )
    external_unconfirmed: Annotated[
        str, "The dataset likely has external backups, but their location is unknown"
    ] = "external_unconfirmed"
    external_confirmed: Annotated[
        str, "The dataset is known to have readily available external sources"
    ] = "external_confirmed"
    uploaded: Annotated[str, "The dataset has been uploaded to sciop"] = "uploaded"


class ScrapeStatus(StrEnum):
    unknown = "unknown"
    not_started = "not_started"
    in_progress = "in_progress"
    completed = "completed"


class SourceType(StrEnum):
    unknown = "unknown"
    web = "web"
    http = "http"
    ftp = "ftp"
    s3 = "s3"


class InputType(StrEnum):
    text = "text"
    textarea = "textarea"
    tokens = "tokens"
