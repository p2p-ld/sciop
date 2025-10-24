"""
Custom macros for jinja templates within docs pages
"""

import typing
from annotated_types import doc, DocInfo
import importlib
import inspect
import textwrap

if typing.TYPE_CHECKING:
    from mkdocs_macros.plugin import MacrosPlugin
    from enum import StrEnum


def define_env(env: "MacrosPlugin"):

    @env.macro
    def documented_enum(module: str, enum_name: str, include_header=False) -> str:
        # not sure why, but mkdocs or something strips annotations from imported objects
        # so we have to reimport
        mod = importlib.import_module(module)
        mod = importlib.reload(mod)
        enum = getattr(mod, enum_name)

        ret = ""

        if include_header:
            name = enum.__name__
            ret += f"### {name}\n"

        for key, val in enum.__annotations__.items():
            # find docstring
            args = typing.get_args(val)
            if not args:
                continue

            docstring = [ann for ann in args if isinstance(ann, DocInfo)]
            if docstring:
                docstring = textwrap.dedent(docstring[0].documentation)
            else:
                continue
            ret += f"- `{key}`: {docstring}\n"

        return ret
