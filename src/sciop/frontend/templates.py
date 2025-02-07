"""
Common source for template environments and decorators
"""

from typing import Literal as L, Optional, TYPE_CHECKING

from fasthx import Jinja
from fastapi.templating import Jinja2Templates
from fastapi import Request

from sciop.api import deps
from sciop.db import get_session
from sciop.config import config, Config
from sciop.const import TEMPLATE_DIR

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


templates = Jinja2Templates(
    directory=TEMPLATE_DIR,
    context_processors=[template_account, template_config],
)

jinja = Jinja(templates)
"""fasthx decorator, see https://github.com/volfpeter/fasthx"""
