import re
from types import UnionType
from typing import Annotated, Any, Union, get_args, get_origin

from pydantic import BaseModel, TypeAdapter
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


def unwrap(typ: type) -> type:
    """
    Unwrap all 'extra' type wrappers to get to the actual type
    """
    typ = unwrap_annotated(typ)
    typ = unwrap_optional(typ)
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


def validate_field(key: str, val: Any, model: type[BaseModel]) -> Any:
    """
    Validate a field within a pydantic model.

    key can be the name of a top-level, scalar key,
    or a nested key with "." as a delimiter
    """
    parts = re.split(r"(?<!\\)\.", key)
    mod = model
    for part in parts[:-1]:
        part = re.sub(r"\\\.", ".", part)
        if part not in mod.model_fields:
            raise KeyError(f"Model {mod} has no such field {part}")
        field = get_model_field(mod.model_fields[part])
        mod = unwrap(field.annotation)
    last_part = re.sub(r"\\\.", ".", parts[-1])
    if last_part not in mod.model_fields:
        raise KeyError(f"Model {mod} has no such field {last_part}")
    field = get_model_field(mod.model_fields[last_part])
    adapter = TypeAdapter(field.annotation)
    return adapter.validate_python(val)
