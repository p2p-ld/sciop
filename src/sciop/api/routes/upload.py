from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Response

from sciop import crud
from sciop.api.auth import create_access_token
from sciop.api.deps import SessionDep, RequireReviewer, RequireUploader
from sciop.config import config
from sciop.models import Account, AccountCreate, Token, Dataset, SuccessResponse
from sciop.logging import init_logger

upload_router = APIRouter(prefix="/upload")


@upload_router.post("/torrent")
def upload_torrent(account: RequireUploader):
    pass
