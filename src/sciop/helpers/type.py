from types import UnionType
from typing import Annotated, Union, get_args, get_origin


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
