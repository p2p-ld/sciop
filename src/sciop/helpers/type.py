from types import UnionType
from typing import Annotated, Union, get_args, get_origin

from pydantic.fields import FieldInfo


def unwrap_optional(typ: type) -> type:
    if get_origin(typ) in (Union, UnionType):
        args = [unwrap_optional(arg) for arg in get_args(typ)]
        for arg in args:
            if arg is not None:
                return arg
    return typ


def unwrap_annotated(typ: type) -> type:
    if get_origin(typ) is Annotated:
        return get_args(typ)[0]
    return typ


def get_model_field(field: FieldInfo) -> FieldInfo:
    """
    Sqlmodel fails to merge Fields when they are set in annotated and the field assignment,
    and it also fails to extract fields inside of Annotated,
    so we have to do that for it.
    """
    ann = unwrap_optional(field.annotation)
    if get_origin(ann) is Annotated:
        items = get_args(ann)
        maybe_field = [item for item in items if isinstance(item, FieldInfo)]
        if len(maybe_field) > 0:
            return maybe_field[0]
    return field
