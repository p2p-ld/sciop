import re
import unicodedata
from typing import TYPE_CHECKING, ClassVar, Optional, TypedDict

import sqlalchemy as sqla
from pydantic import ConfigDict, SecretStr, field_validator
from sqlalchemy.ext.hybrid import hybrid_method, hybrid_property
from sqlalchemy.orm import relationship
from sqlalchemy.schema import UniqueConstraint
from sqlmodel import Field, Relationship, Session, select

from sciop.exceptions import ModerationPermissionsError
from sciop.models.base import SQLModel
from sciop.models.mixins import (
    EnumTableMixin,
    FrontendMixin,
    SearchableMixin,
    TableMixin,
)
from sciop.models.scope import AccountDatasetScopeLink, AccountScopeLink, Scope
from sciop.types import IDField, ModerationAction, Scopes, UsernameStr, UTCDateTime

if TYPE_CHECKING:
    from sciop.models import (
        AuditLog,
        Dataset,
        DatasetClaim,
        DatasetPart,
        ExternalSource,
        Report,
        TorrentFile,
        Upload,
        Webseed,
    )


class AccountScopeLink(TableMixin, table=True):
    __tablename__ = "account_scope_links"
    __table_args__ = (UniqueConstraint("account_id", "scope_id", name="_account_scope_uc"),)

    account_id: Optional[int] = Field(
        default=None, foreign_key="accounts.account_id", primary_key=True, index=True
    )
    scope_id: Optional[int] = Field(
        default=None, foreign_key="scopes.scope_id", primary_key=True, index=True
    )


class AccountBase(SQLModel, FrontendMixin):
    __name__: ClassVar[str] = "account"

    username: UsernameStr

    model_config = ConfigDict(ignored_types=(hybrid_method, hybrid_property))

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

    @property
    def frontend_url(self) -> str:
        return f"/accounts/{self.username}/"

    @hybrid_property
    def short_name(self) -> str:
        return self.username

    @property
    def link_to(self) -> str:
        return f'<a href="{self.frontend_url}">@{self.short_name}</a>'


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
    webseeds: list["Webseed"] = Relationship(back_populates="account")
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
    reports: list["Report"] = Relationship(
        back_populates="target_account",
        sa_relationship=relationship(
            "Report",
            primaryjoin="Account.account_id == Report.target_account_id",
        ),
    )
    opened_reports: list["Report"] = Relationship(
        back_populates="opened_by",
        sa_relationship=relationship(
            "Report",
            primaryjoin="Account.account_id == Report.opened_by_id",
        ),
    )
    resolved_reports: list["Report"] = Relationship(
        back_populates="resolved_by",
        sa_relationship=relationship(
            "Report",
            primaryjoin="Account.account_id == Report.resolved_by_id",
        ),
    )
    is_suspended: bool = False
    claims: list["DatasetClaim"] = Relationship(back_populates="account")

    def can_suspend(self, account: "Account") -> bool:
        """Whether this account can suspend another account"""
        if not self.has_scope("admin"):
            return False

        return not (
            # no self suspensions
            self.username == account.username
            # non-roots can't ban admins
            or (not self.has_scope("root") and account.has_scope("admin"))
            # roots can't ban other roots
            or (self.has_scope("root") and account.has_scope("root"))
        )

    def suspend(self, suspended_by: "Account", session: Session, commit: bool = True) -> None:
        """
        Suspend this account.

        `suspended_by` must be able to suspend this user,
        and will be logged as the actor who suspended the account.
        """
        from sciop import crud

        if not suspended_by.can_suspend(self):
            raise ModerationPermissionsError(
                f"{suspended_by.username} can't suspend {self.username}"
            )

        crud.log_moderation_action(
            session=session, actor=suspended_by, action=ModerationAction.suspend, target=self
        )
        self.is_suspended = True
        session.add(self)
        if commit:
            session.commit()

    def to_read(self) -> "AccountRead":
        return AccountRead.model_validate(self)

    def visible_to(self, account: Optional["Account"] = None) -> bool:
        """Whether this item is visible to the given account"""
        if account is None:
            return not self.is_suspended
        elif self == account:
            return True
        elif account.has_scope("review"):
            return True
        else:
            return not self.is_suspended

    def get_all_items(self, session: Session) -> "AccountItems":
        """
        Get all the items associated with an account.

        Content-bearing items, not including items like moderation actions and etc.
        """
        from sciop.models import Dataset, DatasetPart, Upload

        datasets = list(session.exec(select(Dataset).where(Dataset.account == self)).all())
        dataset_parts = list(
            session.exec(select(DatasetPart).where(DatasetPart.account == self)).all()
        )
        uploads = list(session.exec(select(Upload).where(Upload.account == self)).all())
        return AccountItems(datasets=datasets, dataset_parts=dataset_parts, uploads=uploads)

    def remove_all_items(self, removed_by: "Account", session: Session) -> None:
        """
        Remove all the items associated with an account.

        Each item checks for permissions to remove, since they may be different per-item.

        """
        if not removed_by.has_scope("admin"):
            raise ModerationPermissionsError("Only admins can remove all items from an account")
        items = self.get_all_items(session)
        # remove things that may be children of other things first: uploads, parts, then datasets
        for ul in items["uploads"]:
            ul.remove(account=removed_by, session=session, commit=False)
        for part in items["dataset_parts"]:
            part.remove(account=removed_by, session=session, commit=False)
        for ds in items["datasets"]:
            ds.remove(account=removed_by, session=session, commit=False)
        session.commit()


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


class AccountItems(TypedDict):
    """All items created by an account"""

    datasets: list["Dataset"]
    dataset_parts: list["DatasetPart"]
    uploads: list["Upload"]
