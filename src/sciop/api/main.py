from fastapi import APIRouter

from sciop.api.routes import login_router
from sciop.config import config

api_router = APIRouter(prefix=config.api_prefix)
api_router.include_router(login_router)
