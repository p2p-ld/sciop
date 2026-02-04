from typing import TYPE_CHECKING, Optional

import sqlalchemy as sqla
from pydantic import ConfigDict
from sqlalchemy import ColumnElement
from sqlalchemy.ext.hybrid import hybrid_method, hybrid_property

from sciop.models.base import SQLModel
from sciop.types import Scopes

if TYPE_CHECKING:
    from sciop.models import Account


class ScopedMixin(SQLModel):
    """
    Common columns/properties among scoped objects
    """

    model_config = ConfigDict(ignored_types=(hybrid_method, hybrid_property))

    @hybrid_method
    def has_scope(
        self, *args: str | Scopes, account: Optional["Account"] = None, explicit: bool = False
    ) -> bool:
        """
        Check if an account has a given scope for the object.

        Multiple scopes can be provided as *args,
        return ``True`` if the account has any of the provided scopes.
        """
        if account is None:
            return False
        if account.has_scope("review") and not explicit:
            return True

        str_args = [arg.scope.value if hasattr(arg, "scope") else arg for arg in args]

        if "edit" in str_args and "permissions" not in str_args:
            str_args.append("permissions")

        has_scopes = [scope.scope for scope in self.scopes if scope.account == account]

        return any([scope in has_scopes for scope in str_args])

    @has_scope.inplace.expression
    @classmethod
    def _has_scope(
        cls, *args: str | Scopes, account: Optional["Account"] = None, explicit: bool = False
    ) -> ColumnElement[bool]:
        if account is None:
            return sqla.false()

        or_stmts = [cls.scopes.any(scope=s, account=account) for s in args]

        if not explicit:
            or_stmts.append(account.has_scope("review") == True)

        return sqla.or_(*or_stmts)

    @hybrid_method
    def can_grant_scopes(self, *args: str | Scopes, account: Optional["Account"] = None) -> bool:
        """
        Check if an account can grant the provided scopes for the object.

        Multiple scopes can be provided as *args,
        return ``True`` if the account can grant all of the provided scopes.
        """
        if account is None:
            return False

        str_args = [arg.scope.value if hasattr(arg, "scope") else arg for arg in args]

        return account.has_scope("review") or (
            self.has_scope("permissions", account=account)
            and all(
                [
                    (scope in ["edit", "permissions"] or self.has_scope(scope, account=account))
                    for scope in str_args
                ]
            )
        )

    @can_grant_scopes.inplace.expression
    @classmethod
    def _can_grant_scopes(
        cls, *args: str | Scopes, account: Optional["Account"] = None
    ) -> ColumnElement[bool]:
        if account is None:
            return sqla.false()

        return sqla.or_(
            account.has_scope("review") == True,
            sqla.and_(
                cls.scopes.any(scope="permissions", account=account),
                *[
                    cls.scopes.any(scope=s, account=account)
                    for s in args
                    if s not in ["edit", "permissions"]
                ],
            ),
        )
