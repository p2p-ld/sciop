"""
Common source for template environments and decorators
"""

from types import ModuleType
from typing import TYPE_CHECKING, Optional
from typing import Literal as L

from fastapi import Request
from fastapi.templating import Jinja2Templates
from fasthx import Jinja

from sciop import models, types
from sciop.config import Config, config
from sciop.models.mixins.template import get_environment

if TYPE_CHECKING:
    from sciop.models import Account


def template_account(request: Request) -> dict[L["current_account"], Optional["Account"]]:
    """
    Context processor to automatically feed the current account into templates

    (can only use sync functions in context processors, so can't use deps directly,
    so we can't re-use the reusable oauth2, and mimic its __call__ method)
    """
    return {"current_account": getattr(request.state, "current_account", None)}


def template_config(request: Request) -> dict[L["config"], Config]:
    """no-op context processor to pass config to every template"""
    return {"config": config}


def template_models(request: Request) -> dict[L["models", "types"], ModuleType]:
    return {"models": models, "types": types}


def template_nonce(request: Request) -> dict[L["nonce"], str]:
    return {"nonce": getattr(request.state, "nonce", "")}


templates = Jinja2Templates(
    context_processors=[template_account, template_config, template_models, template_nonce],
    env=get_environment(),
)

jinja = Jinja(templates)
"""fasthx decorator, see https://github.com/volfpeter/fasthx"""
