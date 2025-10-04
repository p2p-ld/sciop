"""
Common source for template environments and decorators
"""

from types import ModuleType
from typing import TYPE_CHECKING, Any, Callable, Optional
from typing import Literal as L

from fastapi import Request
from fastapi.templating import Jinja2Templates
from fasthx.jinja import Jinja

from sciop import models, types
from sciop.config import Config, get_config
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
    return {"config": get_config()}


def template_models(request: Request) -> dict[L["models", "types"], ModuleType]:
    return {"models": models, "types": types}


def template_nonce(request: Request) -> dict[L["nonce"], str]:
    return {"nonce": getattr(request.state, "nonce", "")}


def passthrough_context(key: str) -> Callable:
    """
    Create a context for jinja htmx templates with the returned model as a variable named `key`,
    rather than unpacking the fields of the model.

    Usage:

    ```
    @jinja.hx("some/template.html", make_context=passthrough_context("key"))
    async def some_endpoint(): ...
    ```
    """

    def _passthrough(*, route_result: Any, route_context: Any = None) -> dict[str, Any]:
        return {key: route_result}

    return _passthrough


templates = Jinja2Templates(
    context_processors=[template_account, template_config, template_models, template_nonce],
    env=get_environment(),
)

jinja = Jinja(templates)
"""fasthx decorator, see https://github.com/volfpeter/fasthx"""
