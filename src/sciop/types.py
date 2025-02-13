from enum import StrEnum
from typing import Annotated, Optional, TypeAlias

from annotated_types import Gt

IDField: TypeAlias = Optional[Annotated[int, Gt(0)]]


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
