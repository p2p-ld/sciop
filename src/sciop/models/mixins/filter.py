import re
from datetime import datetime
from logging import Logger
from typing import Annotated, ClassVar, Literal
from urllib.parse import parse_qsl, urlparse

from fastapi import Depends, Query
from pydantic import BaseModel, create_model
from sqlalchemy import Select, func
from sqlalchemy.orm.attributes import QueryableAttribute
from sqlmodel import Field, Session, SQLModel, select
from starlette.datastructures import QueryParams
from starlette.requests import Request

from sciop.logging import init_logger
from sciop.types import FilterType, StringDisplayType

_RANGE_PATTERN = re.compile(r"\[(?P<min>\w+)?(,)?(?P<max>\w+)?\]")


class FilterableCol(SQLModel):
    """
    Configuration of a filterable column.

    Unlike sortable columns, filterable columns may be in joined tables -
    e.g. one might want to filter a dataset by the number of seeds that its uploads have.
    Filters on one->many are OR inclusive - e.g. a dataset will be included in a seed # filter
    if ANY of its uploads are in that range.
    """

    name: str
    filter_type: FilterType
    join: SQLModel | str | None = None
    model: type[SQLModel] | None = None
    string_display: StringDisplayType = StringDisplayType.default


class _RangeTemplateModel(BaseModel):
    filter_type: Literal[FilterType.range]
    name: str
    minimum: int | datetime
    maximum: int | datetime


class _CheckboxTemplateModel(BaseModel):
    filter_type: Literal[FilterType.checkboxes]
    items: list[str]


class FilterTemplateModel(BaseModel):
    """Precooked parameters to pass to the filter partial template"""

    items: dict[str, _RangeTemplateModel | _CheckboxTemplateModel]


class FilterQueryModel(BaseModel):
    cls__: ClassVar[type[BaseModel]]
    cols__: ClassVar[dict[str, FilterableCol]]

    @classmethod
    def from_query_params(cls, query_params: QueryParams) -> "FilterQueryModel":
        params = dict(query_params)
        return cls(**params)

    def apply_filter(self, statement: Select) -> Select:
        logger = init_logger(f"filter.{type(self).__name__}")
        for field_name, field in type(self).model_fields.items():
            value = getattr(self, field_name)
            if not getattr(self, field_name):
                continue

            col = self.cols__.get(field_name)
            if col.join:
                statement = statement.join(col.join)
            model = self.cls__ if col.model is None else col.model
            sql_col = getattr(model, field_name)

            filter_type = field.json_schema_extra.get("filter_type", "default")
            if filter_type == FilterType.range:
                statement = self._apply_range(statement, sql_col, value, logger)
            else:
                logger.warning("Unkonwn filter type: %s", filter_type)
        return statement

    def _apply_range(
        self, statement: Select, field: QueryableAttribute, value: str, logger: Logger
    ) -> Select:
        match = _RANGE_PATTERN.match(value)
        if not match:
            logger.warning("No regex match for range filter for field %s: %s", field, value)
            return statement

        if (range_min := match.groupdict().get("min")) is not None:
            statement = statement.where(field >= int(range_min))
        if (range_max := match.groupdict().get("max")) is not None:
            statement = statement.where(field <= int(range_max))

        return statement


def parse_query_params(request: Request, model: type[FilterQueryModel]) -> FilterQueryModel:
    """
    Get query params if we are called directory or if we are called via some partial in the page
    (and thus the query params will only be in the hx-current-url header)
    """
    if "hx-current-url" in request.headers:
        current_params = parse_qsl(urlparse(request.headers["hx-current-url"]).query)
        query_params = QueryParams(current_params + request.query_params._list)
    else:
        query_params = request.query_params

    return model.from_query_params(query_params)


class FilterMixin(SQLModel):
    """
    Declare how a model's columns should be filtered
    """

    __filterable__: ClassVar[tuple[FilterableCol, ...]] = tuple()
    __query_model__: ClassVar[type[FilterQueryModel]] = None

    @classmethod
    def filter_query_model(cls) -> type[FilterQueryModel]:
        if cls.__query_model__ is None:
            fields = {}
            for f in cls.__filterable__:

                if f.filter_type == FilterType.range:
                    fields[f.name] = (
                        str | None,
                        Field(
                            None,
                            regex=_RANGE_PATTERN.pattern,
                            description="Range string like [0,10]",
                            schema_extra={"json_schema_extra": {"filter_type": f.filter_type}},
                        ),
                    )
                else:
                    fields[f.name] = (
                        str | None,
                        Field(
                            None, schema_extra={"json_schema_extra": {"filter_type": f.filter_type}}
                        ),
                    )
            model = create_model(
                f"FilterQueryModel{cls.__name__}",
                __base__=FilterQueryModel,
                **fields,
            )
            model.cls__ = cls
            model.cols__ = {f.name: f for f in cls.__filterable__}

            cls.__query_model__ = model

        def _dep(
            filter: Annotated[cls.__query_model__, Query()], request: Request
        ) -> cls.__query_model__:
            return parse_query_params(request=request, model=cls.__query_model__)

        return Annotated[
            cls.__query_model__,
            Depends(_dep),
        ]

    @classmethod
    def filter_template_model(cls, session: Session) -> FilterTemplateModel:
        items = {}
        for item in cls.__filterable__:
            if item.filter_type == FilterType.range:
                items[item.name] = cls._range_template_model(item, session)
        return FilterTemplateModel(items=items)

    @classmethod
    def _range_template_model(cls, item: FilterableCol, session: Session) -> _RangeTemplateModel:
        model = cls if item.model is None else item.model
        field = getattr(model, item.name)
        min_max = session.exec(select(func.min(field), func.max(field))).first()
        return _RangeTemplateModel(
            name=item.name, minimum=min_max[0], maximum=min_max[1], filter_type=FilterType.range
        )
