from typing import ClassVar


class FrontendMixin:
    """
    Interface for models that are directly represented in the frontend.

    To be used to reduce the amount of logic in templates and standardize common operations
    like getting short names, urls, etc.
    """

    __name__: ClassVar[str]
    """The human-readable name for the type."""

    @property
    def frontend_url(self) -> str:
        """URL for this item in the frontend - the page where the item can be viewed."""
        raise NotImplementedError()

    @property
    def short_name(self) -> str:
        """
        A short display name for the item, may be separate from the full human-readable name.

        E.g. a dataset's slug, an upload's short hash.
        """
        raise NotImplementedError()

    @property
    def type_name(self) -> str:
        """Human-readable name for the type of an item"""
        return type(self).__name__

    @property
    def link_to(self) -> str:
        """A rendered <a> element linking to the item"""
        return f'<a href="{self.frontend_url}">{self.short_name}</a>'
