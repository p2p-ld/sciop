from enum import Enum
from typing import TYPE_CHECKING, Optional

from sqlmodel import Field, Relationship, SQLModel

from sciop.models.mixin import TableMixin, TableReadMixin

if TYPE_CHECKING:
    from sciop.models import Dataset, DatasetInstance, ExternalInstance, TorrentFile


class AccountBase(SQLModel):
    username: str


class Account(AccountBase, TableMixin, table=True):
    hashed_password: str
    scopes: list["Scope"] = Relationship(back_populates="account")
    datasets: list["Dataset"] = Relationship(back_populates="account")
    submissions: list["DatasetInstance"] = Relationship(back_populates="account")
    external_submissions: list["ExternalInstance"] = Relationship(back_populates="account")
    torrents: list["TorrentFile"] = Relationship(back_populates="account")

    def has_scope(self, scope: str) -> bool:
        return scope in [scope.name.value for scope in self.scopes]


class AccountCreate(AccountBase):
    password: str = Field(min_length=8, max_length=64)


class Scopes(str, Enum):
    submit = "submit"
    upload = "upload"
    review = "review"
    admin = "admin"


class Scope(TableMixin, table=True):
    account_id: Optional[int] = Field(default=None, foreign_key="account.id")
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
