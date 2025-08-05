from enum import StrEnum
from typing import TYPE_CHECKING, Optional

import sqlalchemy as sqla
from pydantic import ConfigDict
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.schema import UniqueConstraint
from sqlmodel import Field, Relationship, select

from sciop.models.base import SQLModel
from sciop.models.mixins import EnumTableMixin, TableMixin
from sciop.types import IDField

if TYPE_CHECKING:
    from sciop.models import (
        Account,
        Dataset,
    )


class AccountScopes(StrEnum):
    """Instance-wide Permissions"""

    submit = "submit"
    """Create new items without review"""
    upload = "upload"
    """Upload new torrents without review"""
    review = "review"
    """Review submissions"""
    admin = "admin"
    """Modify other account scopes, except for demoting/suspending other admins"""
    root = "root"
    """All permissions"""


class ItemScopes(StrEnum):
    """Item-scoped Permissions"""

    edit = "edit"
    """Edit an item"""
    delete = "delete"
    """Delete an item"""


class Scopes(StrEnum):
    """All Permissions"""

    submit = "submit"
    """Create new items without review"""
    upload = "upload"
    """Upload new torrents without review"""
    review = "review"
    """Review submissions"""
    admin = "admin"
    """Modify other account scopes, except for demoting/suspending other admins"""
    root = "root"
    """All permissions"""
    edit = "edit"
    """Edit an item"""
    delete = "delete"
    """Delete an item"""


class AccountScopeLinkBase(SQLModel):
    model_config = ConfigDict(ignored_types=(hybrid_property,))

    account_id: Optional[int] = Field(
        default=None, foreign_key="accounts.account_id", primary_key=True, index=True
    )
    scope_id: Optional[int] = Field(
        default=None, foreign_key="scopes.scope_id", primary_key=True, index=True
    )

    # because scope.scope.scope is too much scope
    @hybrid_property
    def scope(self) -> Scopes:
        return self._scope.scope

    @scope.inplace.expression
    @classmethod
    def scope_expr(cls) -> sqla.SQLColumnExpression[Scopes]:
        return select(Scope.scope).where(Scope.scope_id == cls.scope_id).label("scope")


class AccountScopeLink(AccountScopeLinkBase, TableMixin, table=True):
    __tablename__ = "account_scope_links"
    __table_args__ = (UniqueConstraint("account_id", "scope_id", name="_account_scope_uc"),)


class AccountDatasetScopeLink(AccountScopeLinkBase, TableMixin, table=True):
    __tablename__ = "account_dataset_scope_links"
    __table_args__ = (
        UniqueConstraint("account_id", "scope_id", "dataset_id", name="_account_dataset_scope_uc"),
    )

    dataset_id: Optional[int] = Field(
        default=None, foreign_key="datasets.dataset_id", primary_key=True, index=True
    )
    account: "Account" = Relationship(back_populates="dataset_scopes")
    dataset: "Dataset" = Relationship(back_populates="account_scopes")
    _scope: "Scope" = Relationship(back_populates="account_dataset_links")


class Scope(TableMixin, EnumTableMixin, table=True):
    __tablename__ = "scopes"
    __enum_column_name__ = "scope"

    scope_id: IDField = Field(None, primary_key=True)
    accounts: list["Account"] = Relationship(back_populates="scopes", link_model=AccountScopeLink)
    account_dataset_links: list["AccountDatasetScopeLink"] = Relationship(back_populates="_scope")
    scope: Scopes = Field(unique=True)
