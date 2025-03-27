from types import UnionType
from typing import Union, get_args, get_origin


def unwrap_optional(typ: type) -> type:
    if get_origin(typ) in (Union, UnionType):
        args = [unwrap_optional(arg) for arg in get_args(typ)]
        for arg in args:
            if arg is not None:
                return arg
    return typ
