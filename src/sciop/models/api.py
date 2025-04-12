from typing import Optional
from urllib.parse import quote_plus

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import Select
from starlette.datastructures import QueryParams

from sciop.models.base import SQLModel


class SuccessResponse(BaseModel):
    success: bool
    extra: Optional[dict] = None


class SearchParams(BaseModel):
    """Model for query parameters in a searchable"""

    model_config = ConfigDict(extra="allow")

    query: Optional[str] = Field(None)
    """The search query!"""
    sort: list[str] = Field(default_factory=list)
    """
    Columns to sort by
    
    `colname`, `+colname`: sort ascending
    `-colname`: sort descending
    `*colname`: remove from sort (used by templates,
        using it in an API request usually does nothing)
    """
    page: Optional[int] = None
    size: Optional[int] = None

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
            if sort.startswith("*"):
                continue
            elif sort.startswith("-"):
                sort_items.append(getattr(model, sort[1:]).desc())
            else:
                sort_items.append(getattr(model, sort).asc())
        # clear prior sort and add new one
        return stmt.order_by(None).order_by(*sort_items)
