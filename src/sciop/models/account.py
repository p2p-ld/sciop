import re
import unicodedata
from typing import TYPE_CHECKING, Optional

import sqlalchemy as sqla
from pydantic import ConfigDict, SecretStr, field_validator
from sqlalchemy.ext.hybrid import hybrid_method
from sqlalchemy.orm import relationship
from sqlmodel import Field, Relationship

from sciop.models.base import SQLModel
from sciop.models.mixins import SearchableMixin, TableMixin
from sciop.models.scope import AccountDatasetScopeLink, AccountScopeLink, Scope, Scopes
from sciop.types import IDField, UsernameStr, UTCDateTime

if TYPE_CHECKING:
    from sciop.models import (
        AuditLog,
        Dataset,
        DatasetClaim,
        DatasetPart,
        ExternalSource,
        TorrentFile,
        Upload,
    )


class AccountBase(SQLModel):
    username: UsernameStr

    model_config = ConfigDict(ignored_types=(hybrid_method,))

    @hybrid_method
    def has_scope(self, *args: str | Scopes, dataset_id: Optional[int] = None) -> bool:
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

        str_args = [arg.scope.value if hasattr(arg, "scope") else arg for arg in args]
        str_scopes = [
            a_scope.scope.value if hasattr(a_scope, "scope") else a_scope for a_scope in self.scopes
        ]

        if "root" in str_scopes:
            # root has all scopes implicitly
            return True
        elif "admin" in str_scopes and "root" not in args:
            # admin has all scopes except root implicitly
            return True

        if dataset_id:
            has_scopes = [
                scope.scope for scope in self.dataset_scopes if scope.dataset_id == dataset_id
            ]
        else:
            has_scopes = [scope.scope for scope in self.scopes]

        return any([scope in has_scopes for scope in str_args])

    @has_scope.inplace.expression
    @classmethod
    def _has_scope(cls, *args: str, dataset_id: Optional[int] = None) -> sqla.ColumnElement[bool]:
        if len(args) > 1 and ("root" in args or "admin" in args):
            raise ValueError(
                "root and admin in has_scope checks can only be used by themselves. "
                "They implicitly have all other scopes."
            )
        if "root" in args:
            return cls.scopes.any(scope="root")
        elif "admin" in args:
            return sqla.or_(cls.scopes.any(scope="admin"), cls.scopes.any(scope="root"))

        if dataset_id:
            return sqla.or_(
                *[cls.scopes.any(scope=s) for s in ("root", "admin")],
                *[cls.dataset_scopes.any(scope=s, dataset_id=dataset_id) for s in args],
            )
        else:
            args = ("root", "admin", *args)
            return sqla.or_(*[cls.scopes.any(scope=s) for s in args])

    def get_scope(self, scope: str, dataset_id: Optional[int] = None) -> Optional["Scope"]:
        """Get the scope object from its name and optional item ID, returning None if not present"""
        if dataset_id:
            scope = [
                a_scope
                for a_scope in self.dataset_scopes
                if a_scope.scope.value == scope and a_scope.dataset_id == dataset_id
            ]
        else:
            scope = [a_scope for a_scope in self.scopes if a_scope.scope.value == scope]
        return None if not scope else scope[0]


class Account(AccountBase, TableMixin, SearchableMixin, table=True):
    """A single actor"""

    __tablename__ = "accounts"
    __searchable__ = ["username"]

    account_id: IDField = Field(default=None, primary_key=True)
    hashed_password: str = Field(description="Hashed and salted password")
    scopes: list["Scope"] = Relationship(
        back_populates="accounts",
        sa_relationship_kwargs={"lazy": "selectin"},
        link_model=AccountScopeLink,
    )
    """Permission scopes for this account"""
    datasets: list["Dataset"] = Relationship(back_populates="account")
    dataset_scopes: list["AccountDatasetScopeLink"] = Relationship(back_populates="account")
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
    is_suspended: bool = False
    claims: list["DatasetClaim"] = Relationship(back_populates="account")

    def can_suspend(self, account: "Account") -> bool:
        """Whether this account can suspend another account"""
        if not self.has_scope("admin"):
            return False

        return not (
            self.username == account.username
            or (not self.has_scope("root") and account.has_scope("admin"))
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
    """Filtered account model returned from API methods"""

    scopes: list["Scope"]
    created_at: UTCDateTime


# JSON payload containing access token
class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"


# Contents of JWT token
class TokenPayload(SQLModel):
    sub: str | None = None
