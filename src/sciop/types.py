import re
from enum import StrEnum
from html import escape
from typing import Annotated, Optional, TypeAlias

from annotated_types import Gt, MaxLen
from pydantic import AfterValidator, AnyUrl, BeforeValidator, Field, TypeAdapter
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


class Threat(StrEnum):
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
    text = "text"
    textarea = "textarea"
    tokens = "tokens"
    model_list = "model_list"


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
    val = re.sub(r"^https://doi\.org/", "", val)
    val = re.sub(r"^doi:[/]{,2}", "", val)
    return val


ARK_TYPE: TypeAlias = Annotated[str, Field(pattern=ARK_PATTERN)]
DOI_TYPE: TypeAlias = Annotated[str, BeforeValidator(_strip_doi_prefix), Field(pattern=DOI_PATTERN)]
ISNI_TYPE: TypeAlias = Annotated[str, Field(pattern=ISNI_PATTERN)]
ISSN_TYPE: TypeAlias = Annotated[str, Field(pattern=ISSN_PATTERN)]
QID_TYPE: TypeAlias = Annotated[str, Field(pattern=QID_PATTERN)]


class ExternalIdentifierType(StrEnum):
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
