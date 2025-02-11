from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Optional

from sqlalchemy.orm import relationship
from sqlmodel import Field, Relationship, SQLModel

from sciop.models.mixin import SearchableMixin, TableMixin

if TYPE_CHECKING:
    from sciop.models import (
        AuditLog,
        Dataset,
        Upload,
        ExternalSource,
        Scope,
        TorrentFile,
    )


class Scopes(StrEnum):
    submit = "submit"
    upload = "upload"
    review = "review"
    admin = "admin"


class AccountBase(SQLModel):
    username: str

    def has_scope(self, *args: str | Scopes) -> bool:
        """Check if an account has a given scope."""
        has_scopes = [scope.name.value for scope in self.scopes]
        return any([scope in has_scopes for scope in args])

    def get_scope(self, scope: str) -> Optional["Scope"]:
        """Get the scope object from its name, returning None if not present"""
        scope = [a_scope for a_scope in self.scopes if a_scope.name == scope]
        return None if not scope else scope[0]


class Account(AccountBase, TableMixin, SearchableMixin, table=True):
    __searchable__ = ["username"]
    hashed_password: str
    scopes: list["Scope"] = Relationship(
        back_populates="account", sa_relationship_kwargs={"lazy": "selectin"}
    )
    datasets: list["Dataset"] = Relationship(back_populates="account")
    submissions: list["Upload"] = Relationship(back_populates="account")
    external_submissions: list["ExternalSource"] = Relationship(back_populates="account")
    torrents: list["TorrentFile"] = Relationship(back_populates="account")
    moderation_actions: list["AuditLog"] = Relationship(
        back_populates="actor",
        sa_relationship=relationship(
            "AuditLog",
            primaryjoin="Account.id == AuditLog.actor_id",
        ),
    )
    audit_log_target: list["AuditLog"] = Relationship(
        back_populates="target_account",
        sa_relationship=relationship(
            "AuditLog",
            primaryjoin="Account.id == AuditLog.target_account_id",
        ),
    )


class AccountCreate(AccountBase):
    password: str = Field(min_length=8, max_length=64)


class AccountRead(AccountBase):
    scopes: list["Scope"]
    created_at: datetime


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
