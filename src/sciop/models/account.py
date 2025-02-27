import re
import unicodedata
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Optional

from pydantic import SecretStr, field_validator
from sqlalchemy.orm import relationship
from sqlalchemy.schema import UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel

from sciop.models.mixin import EnumTableMixin, SearchableMixin, TableMixin
from sciop.types import IDField, UsernameStr

if TYPE_CHECKING:
    from sciop.models import (
        AuditLog,
        Dataset,
        DatasetPart,
        ExternalSource,
        TorrentFile,
        Upload,
    )


class Scopes(StrEnum):
    submit = "submit"
    upload = "upload"
    review = "review"
    admin = "admin"
    root = "root"


class AccountScopeLink(TableMixin, table=True):
    __tablename__ = "account_scope_links"
    __table_args__ = (UniqueConstraint("account_id", "scope_id", name="_account_scope_uc"),)

    account_id: Optional[int] = Field(
        default=None, foreign_key="accounts.account_id", primary_key=True
    )
    scope_id: Optional[int] = Field(default=None, foreign_key="scopes.scope_id", primary_key=True)


class AccountBase(SQLModel):
    username: UsernameStr

    def has_scope(self, *args: str | Scopes) -> bool:
        """
        Check if an account has a given scope.

        Multiple scopes can be provided as *args,
        return ``True`` if the account has any of the provided scopes.

        ``root`` and ``admin`` scopes are treated specially:
        - ``root`` accounts have all scopes
        - ``admin`` accounts have all scopes except root

        As a result, one should never need to include ``admin`` and ``root``
        in compound scope checks, and they can only ever be used by themselves
        """
        if len(args) > 1 and ("root" in args or "admin" in args):
            raise ValueError(
                "root and admin in has_scope checks can only be used by themselves. "
                "They implicitly have all other scopes."
            )

        has_scopes = [scope.scope.value for scope in self.scopes]

        if "root" in has_scopes:
            # root has all scopes implicitly
            return True
        elif "admin" in has_scopes and "root" not in args:
            # admin has all scopes except root implicitly
            return True

        return any([scope in has_scopes for scope in args])

    def get_scope(self, scope: str) -> Optional["Scope"]:
        """Get the scope object from its name, returning None if not present"""
        scope = [a_scope for a_scope in self.scopes if a_scope.scope.value == scope]
        return None if not scope else scope[0]


class Account(AccountBase, TableMixin, SearchableMixin, table=True):
    __tablename__ = "accounts"
    __searchable__ = ["username"]

    account_id: IDField = Field(default=None, primary_key=True)
    hashed_password: str
    scopes: list["Scope"] = Relationship(
        back_populates="accounts",
        sa_relationship_kwargs={"lazy": "selectin"},
        link_model=AccountScopeLink,
    )
    datasets: list["Dataset"] = Relationship(back_populates="account")
    dataset_parts: list["DatasetPart"] = Relationship(back_populates="account")
    submissions: list["Upload"] = Relationship(back_populates="account")
    external_submissions: list["ExternalSource"] = Relationship(back_populates="account")
    torrents: list["TorrentFile"] = Relationship(back_populates="account")
    moderation_actions: list["AuditLog"] = Relationship(
        back_populates="actor",
        sa_relationship=relationship(
            "AuditLog",
            primaryjoin="Account.account_id == AuditLog.actor_id",
        ),
    )
    audit_log_target: list["AuditLog"] = Relationship(
        back_populates="target_account",
        sa_relationship=relationship(
            "AuditLog",
            primaryjoin="Account.account_id == AuditLog.target_account_id",
        ),
    )


class AccountCreate(AccountBase):
    password: SecretStr = Field(min_length=12, max_length=64)

    @field_validator("password", mode="after")
    def has_digits(cls, val: SecretStr) -> SecretStr:
        """Has at least two digits, and password not exclusively digits"""
        str_val = val.get_secret_value() if isinstance(val, SecretStr) else val
        n_digits = len(re.findall(r"\d{1}", str_val))

        assert n_digits >= 2, "Passwords must have at least two digits"
        assert n_digits <= len(str_val) - 2, "Passwords must have at least two non-digit characters"

        return val

    @field_validator("password", mode="after")
    def normalize_unicode(cls, val: SecretStr) -> SecretStr:
        """
        Normalize passwords to form C

        idk my dogs if i'm wrong about this hmu

        https://www.unicode.org/reports/tr15/#Stability_of_Normalized_Forms
        https://www.rfc-editor.org/rfc/rfc8265#section-4.2
        """
        return SecretStr(unicodedata.normalize("NFC", val.get_secret_value()))


class AccountRead(AccountBase):
    scopes: list["Scope"]
    created_at: datetime


class Scope(TableMixin, EnumTableMixin, table=True):
    __tablename__ = "scopes"
    __enum_column_name__ = "scope"

    scope_id: IDField = Field(None, primary_key=True)
    accounts: list[Account] = Relationship(back_populates="scopes", link_model=AccountScopeLink)
    scope: Scopes = Field(unique=True)


# JSON payload containing access token
class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"


# Contents of JWT token
class TokenPayload(SQLModel):
    sub: str | None = None
