from enum import Enum
from typing import Optional
from sqlmodel import SQLModel, Field, Relationship
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sciop.models import DatasetInstance


class AccountBase(SQLModel):
    username: str

class Account(AccountBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    password: str
    scopes: list["Scope"] = Relationship(back_populates="account")
    submissions: list["DatasetInstance"] = Relationship(back_populates="submitted_by")

class AccountCreate(AccountBase):
    password: str = Field(min_length=8, max_length=64)


class Scopes(str, Enum):
    submit = "submit"
    admin = "admin"


class Scope(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    account: Account = Relationship(back_populates="scopes")
    name: Scopes


# JSON payload containing access token
class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"


# Contents of JWT token
class TokenPayload(SQLModel):
    sub: str | None = None


class NewPassword(SQLModel):
    token: str
    new_password: str = Field(min_length=8, max_length=64)




