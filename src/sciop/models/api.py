from typing import Optional, TypeVar
from urllib.parse import quote_plus

from fastapi import Query
from fastapi_pagination import Page
from fastapi_pagination.customization import CustomizedPage, UseParams
from fastapi_pagination.default import Params
from pydantic import BaseModel, field_validator
from sqlalchemy import Select
from starlette.datastructures import QueryParams

from sciop.helpers.type import unwrap
from sciop.models.base import SQLModel
from sciop.types import SortableStrEnum

T = TypeVar("T", bound=BaseModel)


class SuccessResponse(BaseModel):
    success: bool
    extra: Optional[dict] = None


class SearchParams(Params):
    """Model for query parameters in a searchable"""

    # model_config = ConfigDict(extra="allow")

    query: Optional[str] = Query(None)
    """The search query!"""
    sort: list[str] = Query(
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
        return any([bool(getattr(self, k, None)) for k in SearchParams.model_fields])

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
        if "sort" in params:
            params["sort"] = cls._clean_sort(params["sort"])
        return SearchParams(**params)

    @classmethod
    def _clean_sort(cls, sort: list[str] | str) -> list[str]:
        if isinstance(sort, str):
            sort = [sort]
        # remove *'s
        sort = [s for s in sort if not s.startswith("*")]
        return sort

    def apply_sort(self, stmt: Select, model: type[SQLModel]) -> Select:
        if not self.sort:
            return stmt

        sort_items = []
        for sort in self.sort:
            desc = False
            if sort.startswith("*"):
                continue
            elif sort.startswith("-"):
                desc = True
                sort = sort[1:]

            # get item

            col = getattr(model, sort)

            try:
                # try to get special types, but don't panic if we can't.
                # that just means it's not a special type we know about!
                annotation = unwrap(model.model_fields[sort].annotation)

                if issubclass(annotation, SortableStrEnum):
                    col = annotation.case_statement(col)
            except (TypeError, KeyError):
                pass

            col = col.desc() if desc else col.asc()
            sort_items.append(col)

        # clear prior sort and add new one
        return stmt.order_by(None).order_by(*sort_items)


SearchPage = CustomizedPage[Page[T], UseParams(SearchParams)]
