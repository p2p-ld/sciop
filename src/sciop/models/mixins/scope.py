from typing import TYPE_CHECKING, ClassVar, Optional

import sqlalchemy as sqla
from pydantic import ConfigDict
from sqlalchemy import ColumnElement
from sqlalchemy.ext.hybrid import hybrid_method, hybrid_property
from sqlmodel import Field, Relationship

from sciop.models.base import SQLModel
from sciop.types import InputType, ItemScopes, Scopes

if TYPE_CHECKING:
    from sciop.models import Account, Dataset, ItemScopeLink


class ScopedMixin(SQLModel):
    """
    Common columns/properties among scoped objects
    """

    model_config = ConfigDict(ignored_types=(hybrid_method, hybrid_property))

    @hybrid_method
    def has_scope(self, *args: str | Scopes, account: Optional["Account"] = None) -> bool:
        """
        Check if an account has a given scope for the object.

        Multiple scopes can be provided as *args,
        return ``True`` if the account has any of the provided scopes.
        """
        if account is None:
            return False

        str_args = [arg.scope.value if hasattr(arg, "scope") else arg for arg in args]

        if "edit" in str_args and "permissions" not in str_args:
            str_args.append("permissions")

        has_scopes = [scope.scope for scope in self.scopes if scope.account == account]

        return any([scope in has_scopes for scope in str_args])

    @has_scope.inplace.expression
    @classmethod
    def _has_scope(
        cls, *args: str | Scopes, account: Optional["Account"] = None
    ) -> ColumnElement[bool]:
        pass

    @hybrid_method
    def can_grant_scopes(
        self, *args: str | Scopes, current_account: Optional["Account"] = None
    ) -> bool:
        """
        Check if an account can grant the provided scopes for the object.

        Multiple scopes can be provided as *args,
        return ``True`` if the account can grant all of the provided scopes.
        """
        if current_account is None:
            return False

        str_args = [arg.scope.value if hasattr(arg, "scope") else arg for arg in args]

        return current_account.has_scope("review") or (
            self.has_scope("permissions", account=current_account)
            and all(
                [
                    (scope == "edit" or self.has_scope(scope, account=current_account))
                    for scope in str_args
                ]
            )
        )

    @can_grant_scopes.inplace.expression
    @classmethod
    def _can_grant_scopes(
        cls, *args: str | Scopes, current_account: Optional["Account"] = None
    ) -> ColumnElement[bool]:
        pass
