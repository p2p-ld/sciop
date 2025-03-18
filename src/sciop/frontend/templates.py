"""
Common source for template environments and decorators
"""

from datetime import UTC, datetime
from types import ModuleType
from typing import TYPE_CHECKING, Optional
from typing import Literal as L

from fastapi import Request
from fastapi.security.utils import get_authorization_scheme_param
from fastapi.templating import Jinja2Templates
from fasthx import Jinja

from sciop import models, types
from sciop.api import deps
from sciop.config import Config, config
from sciop.const import TEMPLATE_DIR
from sciop.db import get_session

if TYPE_CHECKING:
    from sciop.models import Account


def template_account(request: Request) -> dict[L["current_account"], Optional["Account"]]:
    """
    Context processor to automatically feed the current account into templates

    (can only use sync functions in context processors, so can't use deps directly,
    so we can't re-use the reusable oauth2, and mimic its __call__ method)
    """

    token = request.cookies.get("access_token", None)

    # try to get from headers if cookie not present
    if token is None and "Authorization" in request.headers:
        authorization = request.headers.get("Authorization")
        scheme, param = get_authorization_scheme_param(authorization)
        if scheme.lower() == "bearer":
            token = param

    if token is None:
        return {"current_account": None}
    else:
        session = next(get_session())
        account = deps.get_current_account(session, token)
        return {"current_account": account}


def template_config(request: Request) -> dict[L["config"], Config]:
    """no-op context processor to pass config to every template"""
    return {"config": config}


def template_models(request: Request) -> dict[L["models", "types"], ModuleType]:
    return {"models": models, "types": types}


def template_nonce(request: Request) -> dict[L["nonce"], str]:
    return {"nonce": getattr(request.state, "nonce", "")}


templates = Jinja2Templates(
    directory=TEMPLATE_DIR,
    context_processors=[template_account, template_config, template_models, template_nonce],
    trim_blocks=True,
    lstrip_blocks=True,
    autoescape=True,
)
templates.env.globals["models"] = models
templates.env.globals["now"] = datetime.now
templates.env.globals["UTC"] = UTC
templates.env.tests.update(
    {
        "is_list": lambda x: isinstance(x, list),
    }
)

jinja = Jinja(templates)
"""fasthx decorator, see https://github.com/volfpeter/fasthx"""
