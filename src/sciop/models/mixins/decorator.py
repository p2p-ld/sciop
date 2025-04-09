"""
Model decorators for modifying class creation :)
"""

from typing import Callable, Optional, TypeVar

from pydantic_core import PydanticUndefined

from sciop.models.base import SQLModel

T = TypeVar("T", bound=type[SQLModel])


def all_optional(model: T, keep_defaults: bool = False) -> T:
    for _field_name, field in model.__pydantic_fields__.items():
        if not keep_defaults or field.default is PydanticUndefined:
            field.annotation = Optional[field.annotation]
            field.default = None

    if model.__pydantic_complete__:
        model.model_rebuild(force=True)
    return model


def exclude_fields(*args: str) -> Callable[[T], T]:
    def _exclude(model: T) -> T:
        for _field in args:
            del model.__pydantic_fields__[_field]
        if model.__pydantic_complete__:
            model.model_rebuild(force=True)
        return model

    return _exclude
