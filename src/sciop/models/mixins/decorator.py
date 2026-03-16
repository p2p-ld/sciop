"""
Model decorators for modifying class creation :)
"""

from typing import Callable, Optional, TypeVar

from sciop.models.base import SQLModel

T = TypeVar("T", bound=type[SQLModel])


def all_optional(model: T) -> T:
    """Make all fields of a model optional"""

    for _field_name, field in model.__pydantic_fields__.items():
        field.annotation = Optional[field.annotation]
        if field.default_factory is not None:
            field.default_factory = None

        field.default = None

    if model.__pydantic_complete__:
        model.model_rebuild(force=True)
    return model


def exclude_fields(*args: str) -> Callable[[T], T]:
    """Exclude fields from a parent model"""

    def _exclude(model: T) -> T:
        for _field in args:
            del model.__pydantic_fields__[_field]
        if model.__pydantic_complete__:
            model.model_rebuild(force=True)
        return model

    return _exclude
