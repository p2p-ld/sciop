from fastapi import APIRouter
from sciop.config import config
api_router = APIRouter(prefix=config.api_prefix)