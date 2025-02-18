"""
Common source for template environments and decorators
"""

from datetime import UTC, datetime
from types import ModuleType
from typing import TYPE_CHECKING, Optional
from typing import Literal as L

from fastapi import Request
from fastapi.templating import Jinja2Templates
from fasthx import Jinja

from sciop import models
from sciop.api import deps
from sciop.config import Config, config
from sciop.const import TEMPLATE_DIR
from sciop.db import get_session

if TYPE_CHECKING:
    from sciop.models import Account


def template_account(request: Request) -> dict[L["current_account"], Optional["Account"]]:
    """
    Context processor to automatically feed the current account into templates

    (can only use sync functions in context processors, so can't use deps directly

    We are only concerned with cookie-based auth here since this is for frontend templating,
    not the API.
    """
    session = next(get_session())
    token = request.cookies.get("access_token", None)
    if token is None:
        return {"current_account": None}
    else:
        account = deps.get_current_account(session, token)
        return {"current_account": account}


def template_config(request: Request) -> dict[L["config"], Config]:
    """no-op context processor to pass config to every template"""
    return {"config": config}


def template_models(request: Request) -> dict[L["models"], ModuleType]:
    return {"models": models}


def template_nonce(request: Request) -> dict[L["nonce"], str]:
    return {"nonce": getattr(request.state, "nonce", "")}


templates = Jinja2Templates(
    directory=TEMPLATE_DIR,
    context_processors=[template_account, template_config, template_models, template_nonce],
)
templates.env.globals["models"] = models
templates.env.globals["now"] = datetime.now()
templates.env.globals["UTC"] = UTC

jinja = Jinja(templates)
"""fasthx decorator, see https://github.com/volfpeter/fasthx"""
