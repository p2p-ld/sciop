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


class Priority(StrEnum):
    unknown = "unknown"
    low = "low"
    medium = "medium"
    high = "high"


class SourceType(StrEnum):
    unknown = "unknown"
    web = "web"
    http = "http"
    ftp = "ftp"
    s3 = "s3"


class Status(StrEnum):
    todo = "todo"
    claimed = "claimed"
    completed = "completed"


class InputType(StrEnum):
    text = "text"
    textarea = "textarea"
