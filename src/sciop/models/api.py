import re
from typing import Annotated, Any, ClassVar, Optional, Self, TypeVar
from typing import Literal as L
from urllib.parse import quote_plus

import sqlalchemy as sqla
from fastapi import Query
from fastapi_pagination import Page
from fastapi_pagination.bases import RawParams
from fastapi_pagination.customization import CustomizedPage, UseParams
from fastapi_pagination.default import Params
from pydantic import AfterValidator, BaseModel, Field, GetCoreSchemaHandler, field_validator
from pydantic_core import CoreSchema, core_schema
from sqlalchemy import Select
from starlette.datastructures import QueryParams

from sciop.helpers.type import unwrap
from sciop.models.base import SQLModel
from sciop.types import SortableStrEnum

T = TypeVar("T", bound=BaseModel)


class SuccessResponse(BaseModel):
    success: bool
    extra: Optional[dict] = None


class SortStr(str):
    type: ClassVar[str] = None
    """The type of sort this is!"""
    pattern: ClassVar[re.Pattern] = None

    @classmethod
    def match(cls, value: str) -> Self | None:
        assert cls.pattern.fullmatch(value), "Does not match sort type pattern!"
        return cls(value)

    @property
    def field(self) -> str:
        """The item name without any prefixes"""
        return self.pattern.match(self).groupdict()["field"]

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: GetCoreSchemaHandler
    ) -> CoreSchema:
        return core_schema.no_info_after_validator_function(
            function=cls.match,
            schema=core_schema.str_schema(
                pattern=cls.pattern.pattern, metadata={"sort_type": cls.type}
            ),
        )


class AscendingSort(SortStr):
    type: ClassVar[L["ascending"]] = "ascending"
    pattern: ClassVar[re.Pattern] = re.compile(r"(?P<field>[\w-]+)")


class DescendingSort(SortStr):
    type: ClassVar[L["descending"]] = "descending"
    pattern: ClassVar[re.Pattern] = re.compile(r"^-(?P<field>[\w-]+)")


class RemoveSort(SortStr):
    """Special query param type that removes the item from sorting, used in partials"""

    type: ClassVar[L["remove"]] = "remove"
    pattern: ClassVar[re.Pattern] = re.compile(r"^\*(?P<field>[\w-]+)")

    @classmethod
    def match(cls, value: str) -> Self | None:
        """RemoveSort is just a None"""
        assert cls.pattern.fullmatch(value), "Does not match sort type pattern!"
        return None


SortStrType = Annotated[
    RemoveSort | DescendingSort | AscendingSort, Field(union_mode="left_to_right")
]


def _remove_none(value: list[SortStrType]) -> list[SortStrType]:
    return [v for v in value if v and v is not None and not isinstance(v, RemoveSort)]


SortParamsType = Annotated[list[SortStrType], AfterValidator(_remove_none)]


class SearchParams(Params):
    """Model for query parameters in a searchable"""

    # model_config = ConfigDict(extra="allow")

    query: Optional[str] = Query(None)
    """The search query!"""
    sort: SortParamsType = Query(
        default_factory=list,
        description="""
        Columns to sort by
        
        Syntax: 
        
        `colname`, `+colname`: sort ascending
        `-colname`: sort descending
        `*colname`: remove from sort (used by templates,
            using it in an API request usually does nothing)
        """,
    )

    @field_validator("sort", mode="before")
    @classmethod
    def str_to_list(cls, val: str | list[str]) -> list[str]:
        return val if isinstance(val, list) else [val]

    def should_redirect(self) -> bool:
        """Whether we have query parameters that should be included in HX-Replace-Url"""
        params = self.model_dump(exclude_none=True, exclude_defaults=True, exclude={"size"})
        return any([bool(v) for v in params.values()])

    def to_query_str(self) -> str:
        value = self.model_dump(exclude_none=True, exclude_unset=True, exclude_defaults=True)
        if "sort" in value and value["sort"]:
            value["sort"] = ",".join([v for v in value["sort"] if not v.startswith("*")])
        parts = ["=".join([quote_plus(k), quote_plus(str(v))]) for k, v in value.items() if v]
        query = "?" + "&".join(parts) if parts else ""
        return query

    @classmethod
    def from_query_params(cls, query_params: QueryParams) -> "SearchParams":
        """
        Parse query params, replacing or updating any query params from e.g. the current url
        """
        params = dict(query_params)
        if isinstance(params.get("sort"), str):
            params["sort"] = [params["sort"]]
        if params.get("query") == "":
            del params["query"]
        return SearchParams(**params)

    def apply_sort(self, stmt: Select, model: type[SQLModel]) -> Select:
        if not self.sort:
            return stmt

        sort_items = []
        for sort in self.sort:
            desc = False
            if sort.type == "remove":
                continue
            elif sort.type == "descending":
                desc = True
                sort = sort.field

            # get item if we have it
            col = getattr(model, sort, None)
            if col is None:
                continue

            try:
                # try to get special types, but don't panic if we can't.
                # that just means it's not a special type we know about!
                annotation = unwrap(model.model_fields[sort].annotation)

                if issubclass(annotation, SortableStrEnum):
                    col = annotation.case_statement(col)
            except (TypeError, KeyError):
                pass

            col = sqla.desc(col.collate("NOCASE")) if desc else sqla.asc(col.collate("NOCASE"))
            sort_items.append(col)

        # clear prior sort and add new one
        return stmt.order_by(None).order_by(*sort_items)

    def sorted_by(self, field: str) -> L["remove", "descending", "ascending"] | None:
        """Get the sort type, if any, for the given field"""
        match = [sorted for sorted in self.sort if sorted.field == field]
        if match:
            return match[0].type
        else:
            return None


class RaggedPageParams(Params):
    """
    Page that has a smaller number of items in the first page
    Allow "size" to be None - if size is None, use the ragged params.
    If size is explicitly passed, use that to calculate offset, ignoring ragged params
    """

    page: int = Query(1, ge=1)
    size: int | None = Query(None, ge=1, le=5000)
    first_size: int = Query(100, ge=1, le=500)
    other_size: int = Query(1000, ge=1, le=5000)

    def to_raw_params(self) -> RawParams:
        offset = None
        if self.size:
            if self.page is not None:
                offset = self.size * (self.page - 1)
            limit = self.size
        else:
            if self.page == 1:
                limit = self.first_size
            else:
                limit = self.other_size
                offset = self.first_size + ((self.page - 2) * self.other_size)

        return RawParams(
            limit=limit,
            offset=offset,
        )


class RaggedSearchPage(RaggedPageParams, SearchParams):
    """
    Combination of ragged page params and search params
    """


SearchPage = CustomizedPage[Page[T], UseParams(SearchParams)]
RaggedSearchPage = CustomizedPage[Page[T], UseParams(RaggedSearchPage)]
