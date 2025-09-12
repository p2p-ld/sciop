import re
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from html import escape
from os import PathLike as PathLike_
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Literal, Optional, TypeAlias, Union

import sqlalchemy as sqla
from annotated_types import Gt, MaxLen, MinLen
from pydantic import AfterValidator, AnyUrl, BeforeValidator, PlainSerializer, TypeAdapter
from slugify import slugify
from sqlalchemy import Case, ColumnElement, case
from sqlmodel import Field

if TYPE_CHECKING:
    from sciop.models import Account

USERNAME_PATTERN = re.compile(r"^[\w-]+$")
"""Only word characters and hyphens"""


def _validate_username(username: str) -> str:
    assert USERNAME_PATTERN.fullmatch(
        username
    ), f"{username} is not a valid username, must match {USERNAME_PATTERN.pattern}"
    return username


def _validate_no_traversal(path: PathLike_) -> PathLike_:
    posix = Path(path).as_posix()
    assert "/" not in posix, "Filesystem paths cannot have path separators in them"
    return path


def _delta_from_minutes(minutes: int | timedelta) -> timedelta:
    if isinstance(minutes, (int, float)):
        minutes = timedelta(minutes=minutes)
    return minutes


def _minutes_from_delta(delta: timedelta) -> int:
    return int(delta.total_seconds() / 60)


IDField: TypeAlias = Optional[Annotated[int, Gt(0)]]
"""An >0 integer to be used as a db ID"""
EscapedStr: TypeAlias = Annotated[str, AfterValidator(escape)]
"""String that has been html-escaped"""
SlugStr: TypeAlias = Annotated[str, AfterValidator(slugify)]
"""A slufified string, with only lowercase letters and hyphens"""
AnyUrlTypeAdapter = TypeAdapter(AnyUrl)
MaxLenURL = Annotated[
    str, MaxLen(512), AfterValidator(lambda url: str(AnyUrlTypeAdapter.validate_python(url)))
]
"""URL that is at most 512 characters long"""
PathLike = Annotated[PathLike_[str], AfterValidator(lambda x: Path(x).as_posix())]
"""Path-like string, as a POSIX path"""
FileName = Annotated[str, AfterValidator(_validate_no_traversal)]
"""A filename that can't ascend above its current directory"""
UTCDateTime = Annotated[datetime, AfterValidator(lambda x: x.replace(tzinfo=UTC))]
"""
Datetime object that is cast to UTC

# although this does not get applied when models are reloaded,
# as it seems like values are populated by assignment, and we have validate_assignment=False
"""
DeltaMinutes = Annotated[
    timedelta, BeforeValidator(_delta_from_minutes), PlainSerializer(_minutes_from_delta)
]
"""
Serializable timedeltas from (integer) minutes.
"""


def _username_col() -> sqla.Column:
    return sqla.Column(
        sqla.String(64, collation="NOCASE"),
        index=False,  # unique creates an internal index
        nullable=False,
        unique=True,
    )


def _extract_username(val: Union[str, "Account"]) -> str:
    from sciop.models import Account

    if isinstance(val, Account):
        return val.username
    return val


UsernameStr: TypeAlias = Annotated[
    str,
    MinLen(1),
    MaxLen(64),
    # Need a specific functional validator because sqlmodel regex validation is busted
    BeforeValidator(_extract_username),
    AfterValidator(_validate_username),
    Field(
        ...,
        regex=USERNAME_PATTERN.pattern,
        sa_column=_username_col(),
    ),
]
"""Allowable usernames"""


class SortableStrEnum(StrEnum):
    """StrEnum that can declare its sort order for an order_by statement"""

    __sort_order__: dict[str, int] | None = None
    """
    Specify an explicit sort order, 
    rather than using the implicit ordering of member declaration 

    Examples:

        {
            "value_1": 0,
            "value_3": 2,
            "value_2": 1
        }
    """

    @classmethod
    def case_statement(cls, col: ColumnElement) -> Case:
        """
        Case statement to be used with an order_by statement

        Examples:

            order_by(MyEnum.case_statement(MyModel.my_enum))

        """
        order = cls.__sort_order__
        if order is None:
            order = {v: idx for idx, v in enumerate(cls.__members__.values())}
        return case(order, value=col)


class AccessType(StrEnum):
    """How an item is allowed to be accessed"""

    unknown = "unknown"
    """idk"""
    public = "public"
    """Can be accessed by anyone"""
    registration = "registration"
    """Requires at least some account to be created"""
    paywalled = "paywalled"
    """Requires payment"""
    proprietary = "proprietary"
    """Specific access must be granted, if it is at all"""


class Scarcity(StrEnum):
    """How abundant an item is copied, or how likely an item is to be recoverable"""

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
    """The progress in preserving an item"""

    unknown = "unknown"
    not_started = "not_started"
    in_progress = "in_progress"
    completed = "completed"


class SourceType(StrEnum):
    """What form the current item is accessible in"""

    unknown = "unknown"
    web = "web"
    http = "http"
    ftp = "ftp"
    s3 = "s3"
    bittorrent = "bittorrent"


class Threat(SortableStrEnum):
    """
    How likely something is to become unavailable at its original source,
    or whether there are likely to be barriers to freely accessing it.
    """

    unknown: Annotated[str, "Threat is unknown"] = "unknown"
    indefinite: Annotated[str, "Baseline threat level, no clear time or threat of removal"] = (
        "indefinite"
    )
    watchlist: Annotated[
        str,
        (
            "Content is at risk by its nature, either the topic or publisher, "
            "but no specific threat has been made"
        ),
    ] = "watchlist"
    endangered: Annotated[
        str,
        (
            "This item in particular is likely to be removed soon, but takedown has not been "
            "issued. This item should be preserved pre-emptively if no higher-threat items exist."
        ),
    ] = "endangered"
    takedown_issued: Annotated[
        str,
        (
            "This item has had a specific takedown notice issued for it, "
            "and must be preserved immediately"
        ),
    ] = "takedown_issued"
    extinct: Annotated[str, "Threat has been realized, source no longer exists"] = "extinct"


class InputType(StrEnum):
    """The input type to render for a model field when used in a form"""

    input = "input"
    select = "select"
    textarea = "textarea"
    tokens = "tokens"
    model_list = "model_list"
    none = "none"


ARK_PATTERN = r"^\S*ark:\S+"
"""
Entirely incomplete pattern just to recognize ark vs not ark
See: https://arks.org/specs/
"""

DOI_PATTERN = r"^10\.\d{3,9}\/[-._;()/:A-Za-z0-9]+$"
"""
https://www.crossref.org/blog/dois-and-matching-regular-expressions/
"""

ISNI_PATTERN = r"^[0-9]{15}[0-9X]$"
ISSN_PATTERN = r"^[0-9]{4}-[0-9]{3}[0-9X]$"
QID_PATTERN = r"^Q\d+$"


def _strip_doi_prefix(val: str) -> str:
    val = val.strip()
    val = re.sub(r"^https?://(:?dx\.)?doi\.org/", "", val)
    val = re.sub(r"^doi:[/]{,2}", "", val)
    return val


ARK_TYPE: TypeAlias = Annotated[str, Field(regex=ARK_PATTERN)]
DOI_TYPE: TypeAlias = Annotated[str, BeforeValidator(_strip_doi_prefix), Field(regex=DOI_PATTERN)]
ISNI_TYPE: TypeAlias = Annotated[str, Field(regex=ISNI_PATTERN)]
ISSN_TYPE: TypeAlias = Annotated[str, Field(regex=ISSN_PATTERN)]
QID_TYPE: TypeAlias = Annotated[str, Field(regex=QID_PATTERN)]


class ExternalIdentifierType(StrEnum):
    """Recognized external and persistent identifiers"""

    ark: Annotated[ARK_TYPE, "Archival Resource Key"] = "ark"
    cid: Annotated[str, "IPFS/IPLD Content Identifier"] = "cid"
    doi: Annotated[DOI_TYPE, "Digital Object Identifier"] = "doi"
    isni: Annotated[ISNI_TYPE, "International Standard Name Identifier "] = "isni"
    isbn: Annotated[str, "International Standard Book Number"] = "isbn"
    issn: Annotated[ISSN_TYPE, "International Standard Serial Number"] = "issn"
    purl: Annotated[AnyUrl, "Persistent Uniform Resource Locator"] = "purl"
    qid: Annotated[QID_TYPE, "Wikidata Identifier"] = "qid"
    rrid: Annotated[str, "Research Resource Identifier"] = "rrid"
    urn: Annotated[str, "Uniform Resource Name"] = "urn"
    uri: Annotated[str, "Uniform Resource Identifier"] = "uri"
    orcid: Annotated[str, "Open Researcher and Contributor ID"] = "orcid"


RDFSuffixType: TypeAlias = Literal["ttl", "rdf", "nt", "json"]
suffix_to_ctype = {
    "html": "text/html",
    "xhtml": "application/xhtml+xml",
    "rss": "application/rss+xml",
    "ttl": "text/turtle",
    "rdf": "application/rdf+xml",
    "nt": "application/n-triples",
    "json": "application/ld+json",
}
ctype_to_suffix = {v: k for k, v in suffix_to_ctype.items()}


class Scopes(StrEnum):
    """Account Permissions"""

    submit = "submit"
    """Create new items without review"""
    upload = "upload"
    """Upload new torrents without review"""
    review = "review"
    """Review submissions"""
    admin = "admin"
    """Modify other account scopes, except for demoting/suspending other admins"""
    root = "root"
    """All permissions"""
