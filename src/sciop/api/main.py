from fastapi import APIRouter
from sciop.config import config

from sciop.api.routes import login_router
api_router = APIRouter(prefix=config.api_prefix)
api_router.include_router(login_router)