from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt
from pydantic import SecretStr

from sciop.config import get_config

ALGORITHM = "HS256"


def create_access_token(subject: str | Any, expires_delta: timedelta) -> str:
    expire = datetime.now(UTC) + expires_delta
    to_encode = {"exp": expire, "sub": str(subject)}
    encoded_jwt = jwt.encode(
        to_encode, get_config().secret_key.get_secret_value(), algorithm=ALGORITHM
    )
    return encoded_jwt


def verify_password(plain_password: str | SecretStr, hashed_password: str) -> bool:
    if isinstance(plain_password, SecretStr):
        return bcrypt.checkpw(
            plain_password.get_secret_value().encode("utf-8"), hashed_password.encode("utf-8")
        )

    else:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def get_password_hash(password: str | SecretStr) -> str:
    if isinstance(password, SecretStr):
        return bcrypt.hashpw(password.get_secret_value().encode("utf-8"), bcrypt.gensalt()).decode(
            "utf-8"
        )
    else:
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
