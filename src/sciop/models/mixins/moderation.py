import hashlib
from datetime import datetime
from typing import TYPE_CHECKING, Optional

import sqlalchemy as sqla
from pydantic import ConfigDict
from sqlalchemy import ColumnElement
from sqlalchemy.ext.hybrid import hybrid_method, hybrid_property
from sqlmodel import Field, Session

from sciop.exceptions import ModerationPermissionsError
from sciop.models.base import SQLModel
from sciop.types import InputType, ItemScopes, ModerationAction

if TYPE_CHECKING:
    from sciop.models import Account


class ModerableMixin(SQLModel):
    """
    Common columns/properties among moderable objects
    """

    is_approved: bool = Field(
        False,
        description="Whether this item has been reviewed and is now visible",
        schema_extra={"json_schema_extra": {"input_type": InputType.none}},
    )
    is_removed: bool = Field(
        False,
        description="Whether the item has been, for all practical purposes, deleted.",
        schema_extra={"json_schema_extra": {"input_type": InputType.none}},
    )

    model_config = ConfigDict(ignored_types=(hybrid_method, hybrid_property))

    # TODO: https://github.com/fastapi/sqlmodel/issues/299#issuecomment-2223569400
    @hybrid_property
    def is_visible(self) -> bool:
        """Whether the dataset should be displayed and included in feeds"""
        return self.is_approved and not self.is_removed

    @is_visible.inplace.expression
    @classmethod
    def _is_visible(cls) -> ColumnElement[bool]:
        return sqla.and_(cls.is_approved == True, cls.is_removed == False)

    @hybrid_property
    def needs_review(self) -> bool:
        """Whether a dataset needs to be reviewed"""
        return not self.is_approved and not self.is_removed

    @needs_review.inplace.expression
    @classmethod
    def _needs_review(cls) -> ColumnElement[bool]:
        return sqla.and_(cls.is_approved == False, cls.is_removed == False)

    @hybrid_method
    def visible_to(self, account: Optional["Account"] = None) -> bool:
        """Whether this item is visible to the given account"""
        if account is None:
            return self.is_visible
        if self.is_visible:
            return True
        elif self.is_removed:
            return False
        elif hasattr(self, "account") and self.account == account:
            return True
        elif hasattr(self, "scopes") and self.has_scope(
            *[s.value for s in ItemScopes], account=account
        ):
            return True
        else:
            return account.has_scope("review")

    @visible_to.inplace.expression
    @classmethod
    def _visible_to(cls, account: Optional["Account"] = None) -> ColumnElement[bool]:
        if account is None:
            return cls._is_visible

        or_stmts = [cls.is_visible == True, account.has_scope("review") == True]

        if hasattr(cls, "account"):
            or_stmts.append(cls.account == account)

        if hasattr(cls, "scopes"):
            or_stmts.append(cls.has_scope(*[s.value for s in ItemScopes], account=account) == True)

        return sqla.and_(
            cls.is_removed == False,
            sqla.or_(*or_stmts),
        )

    @hybrid_method
    def removable_by(self, account: Optional["Account"] = None) -> bool:
        if account is None:
            return False
        return (
            (hasattr(self, "account") and self.account == account)
            or (hasattr(self, "scopes") and self.has_scope("delete", account=account))
            or account.has_scope("review")
        )

    @removable_by.inplace.expression
    @classmethod
    def _removable_by(cls, account: Optional["Account"] = None) -> ColumnElement[bool]:
        if account is None:
            return sqla.false()

        or_stmts = [account.has_scope("review") == True]

        if hasattr(cls, "account"):
            or_stmts.append(cls.account == account)

        if hasattr(cls, "scopes"):
            or_stmts.append(cls.has_scope("delete", account=account) == True)

        return sqla.or_(*or_stmts)

    def hide(self, account: "Account", session: Session, commit: bool = True) -> None:
        """
        Hide the item - rendering it publicly invisible but preserving it in the database

        Required permissions are same as `removable_by`
        """
        from sciop.crud import log_moderation_action

        if not self.removable_by(account):
            raise ModerationPermissionsError(f"{account.username} not permitted to hide this item")
        log_moderation_action(
            session=session, actor=account, target=self, action=ModerationAction.hide
        )
        self.is_approved = False
        session.add(self)
        if commit:
            session.commit()

    def remove(self, account: "Account", session: Session, commit: bool = True) -> None:
        """
        Remove the item, preserving necessary database remnants for internal references,
        but for all intents and purposes rendering the item 'deleted.'
        """
        from sciop.crud import log_moderation_action
        from sciop.types import ModerationAction

        if not self.removable_by(account):
            raise ModerationPermissionsError(
                f"{account.username} not permitted to remove this item"
            )
        log_moderation_action(
            session=session,
            actor=account,
            target=self,
            action=ModerationAction.remove,
            commit=commit,
        )
        self.is_removed = True
        session.add(self)
        if commit:
            session.commit()

    @staticmethod
    def _add_prefix(val: str, timestamp: datetime, key: str) -> str:
        # underscores can only get in slugs through prefix events
        if "__" in val:
            return val
        hasher = hashlib.blake2b(digest_size=3)
        hasher.update(timestamp.isoformat().encode("utf-8"))
        hash = hasher.hexdigest()
        return f"{hash}-{key.upper()}__{val}"

    @staticmethod
    def _remove_prefix(val: str) -> str:
        if "__" in val:
            return val.split("__", 1)[1]
        else:
            return val
