import ctypes
import os
from enum import Enum
from pathlib import Path
from typing import Callable as C
from typing import Optional, cast

import click
import pydantic_core

from sciop.helpers.type import unwrap_optional
from sciop.models.mixins import TemplateModel

CLICK_TYPE_MAP = {
    Path: click.Path,
    Enum: click.Choice,
}


def is_root() -> bool:
    """
    Checks if we are root on unix and windows systems.

    Mildly modified to get effective uid on unix rather than uid

    References:
        https://raccoon.ninja/post/dev/using-python-to-check-if-the-application-is-running-as-an-administrator/
    """
    try:
        is_admin = os.geteuid() == 0
    except AttributeError:
        is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
    return is_admin


def ensure_nonroot() -> None:
    """Ensure that the current user is not root, raising if so"""
    try:
        if is_root():
            raise click.UsageError(
                message="Command cannot be run as root or administrator! "
                "Nothing in sciop should be run as root :)"
            )
    except Exception as e:
        proceed = click.prompt(
            "Could not detect whether user is root. "
            "Sciop commands should not be run as root. Run anyway? "
            "[y/n]",
            default="n",
        )
        if not proceed.strip().lower() == "y":
            raise e


def _map_click_type(typ: type) -> Optional[type]:
    typ = unwrap_optional(typ)
    target_type = CLICK_TYPE_MAP.get(typ, typ)
    if target_type is click.Choice:
        typ = cast(Enum, typ)
        target_type = target_type(list(typ.__members__.keys()))
    elif target_type is click.Path:
        target_type = target_type()
    return target_type


def model_options(model: type[TemplateModel]) -> C[[click.Command], click.Command]:
    """Inject fields from a pydantic model as cli command input"""

    def decorator(f: click.Command) -> click.Command:
        nonlocal model
        for field_name, field in model.model_fields.items():
            option_kwargs = {
                "type": _map_click_type(field.annotation),
                "help": field.description,
                "required": field.is_required(),
                "show_default": True,
            }

            if field.default is not pydantic_core.PydanticUndefined:
                option_kwargs["default"] = field.default

            f.params.append(click.Option((f"--{field_name}",), **option_kwargs))
        return f

    return decorator


def config_option(f: click.Command) -> click.Command:
    f = click.option(
        "-c",
        "--config",
        type=click.Path(exists=True, dir_okay=False),
        help="Path to sciop.yaml or .env file. If none, look in current directory",
    )(f)
    return f
