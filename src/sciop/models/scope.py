from typing import TYPE_CHECKING, Optional

import sqlalchemy as sqla
from pydantic import BaseModel
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.schema import UniqueConstraint
from sqlmodel import Field, Relationship, Session, select

from sciop.models.mixins import EnumTableMixin, TableMixin
from sciop.types import IDField, Scopes

if TYPE_CHECKING:
    from sciop.models import (
        Account,
        Dataset,
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


class ItemScopeLink(TableMixin, table=True):
    __tablename__ = "item_scope_links"
    __table_args__ = (
        UniqueConstraint(
            "account_id", "dataset_id", "scope_id", name="_account_id_dataset_id_scope_id_uc"
        ),
    )

    item_scope_link_id: IDField = Field(default=None, primary_key=True)
    account_id: Optional[int] = Field(
        default=None, foreign_key="accounts.account_id", index=True, nullable=True
    )
    dataset_id: Optional[int] = Field(
        default=None, foreign_key="datasets.dataset_id", index=True, nullable=True
    )
    scope_id: Optional[int] = Field(default=None, foreign_key="scopes.scope_id", index=True)
    account: "Account" = Relationship(back_populates="item_scopes")
    dataset: "Dataset" = Relationship(back_populates="scopes")
    _scope: "Scope" = Relationship(back_populates="item_scope_links")

    # because scope.scope.scope is too much scope
    @hybrid_property
    def scope(self) -> Scopes:
        return self._scope.scope

    @scope.inplace.expression
    @classmethod
    def scope_expr(cls) -> sqla.SQLColumnExpression[Scopes]:
        return select(Scope.scope).where(Scope.scope_id == cls.scope_id).label("scope")


class Scope(TableMixin, EnumTableMixin, table=True):
    __tablename__ = "scopes"
    __enum_column_name__ = "scope"

    scope_id: IDField = Field(None, primary_key=True)
    accounts: list["Account"] = Relationship(back_populates="scopes", link_model=AccountScopeLink)
    item_scope_links: list["ItemScopeLink"] = Relationship(back_populates="_scope")
    scope: Scopes = Field(unique=True)


class ItemScope(BaseModel):
    """Aggregated-by-account scopes object returned from API methods"""

    username: str
    scopes: list[str] = []

    def to_links(self, dataset: "Dataset", session: Session) -> list[ItemScopeLink]:
        account = session.exec(select(Account).where(Account.username == self.username)).first()
        if not account:
            raise ValueError("Account not found: " + self.username)
        return [
            ItemScopeLink(account=account, dataset=dataset, _scope=Scope.get_item(scope, session))
            for scope in self.scopes
        ]

    @classmethod
    def from_links(cls, links: list[ItemScopeLink]) -> list["ItemScope"]:
        return [
            ItemScope(
                username=username,
                scopes=[link.scope.value for link in links if link.account.username == username],
            )
            for username in list(dict.fromkeys([s.account.username for s in links]))
        ]

    @classmethod
    def from_dict(cls, dict: dict) -> list["ItemScope"]:
        return [
            ItemScope(username=scope["username"], scopes=scope["scopes"])
            for scope in dict
            if "scopes" in scope
        ]
