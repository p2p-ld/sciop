from typing import TYPE_CHECKING, Optional

import sqlalchemy as sqla
from pydantic import ConfigDict
from sqlalchemy import ColumnElement
from sqlalchemy.ext.hybrid import hybrid_method, hybrid_property
from sqlmodel import Field

from sciop.models.base import SQLModel
from sciop.types import InputType

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
        else:
            return account.has_scope("review")

    @visible_to.inplace.expression
    @classmethod
    def _visible_to(cls, account: Optional["Account"] = None) -> ColumnElement[bool]:
        if account is None:
            return cls._is_visible

        if hasattr(cls, "account"):
            return sqla.and_(
                cls.is_removed == False,
                sqla.or_(
                    cls.is_visible == True,
                    account.has_scope("review") == True,
                    cls.account == account,
                ),
            )
        else:
            return sqla.and_(
                cls.is_removed == False,
                sqla.or_(cls.is_visible == True, account.has_scope("review") == True),
            )

    @hybrid_method
    def removable_by(self, account: Optional["Account"] = None) -> bool:
        if account is None:
            return False
        return self.account == account or account.has_scope("review")

    @removable_by.inplace.expression
    @classmethod
    def _removable_by(cls, account: Optional["Account"] = None) -> ColumnElement[bool]:
        if account is None:
            return sqla.false()
        return sqla.or_(cls.account == account, account.has_scope("review") == True)
