from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypeVar

import bleach
import mistune
from mistune.plugins.table import table
from pygments import highlight
from pygments.formatters import html
from pygments.lexers import get_lexer_by_name

if TYPE_CHECKING:
    from sqlalchemy.orm import Connection, Mapper
    from sqlalchemy.orm.attributes import InstrumentedAttribute
    from sqlmodel import SQLModel

    _O = TypeVar("_O", bound=SQLModel)

MAX_HEADING_LEVEL = 4

ALLOWED_TAGS = (bleach.sanitizer.ALLOWED_TAGS - {"a"}) | {
    *(f"h{level+1}" for level in range(MAX_HEADING_LEVEL)),
    "p",
    "table",
    "tr",
    "th",
    "td",
    "tbody",
    "tfoot",
    "thead",
    "span",
    "details",
    "summary",
}


_cleaner = bleach.Cleaner(tags=ALLOWED_TAGS, attributes={})


class HighlightRenderer(mistune.HTMLRenderer):
    """
    References:
        https://mistune.lepture.com/en/latest/guide.html#customize-renderer
    """

    def block_code(self, code: str, info: str | None = None) -> str:
        if not info:
            return f"\n<pre><code>{mistune.escape(code)}</code></pre>\n"
        lexer = get_lexer_by_name(info, stripall=True)
        formatter = html.HtmlFormatter(lineseparator="<br>")
        return highlight(code, lexer, formatter)

    def inline_html(self, html: str) -> str:
        return _cleaner.clean(html)

    def block_html(self, html: str) -> str:
        return _cleaner.clean(html)

    def heading(self, text: str, level: int, **attrs: Any) -> str:
        if level > MAX_HEADING_LEVEL:
            return self.strong(text, **attrs)
        return super().heading(text, level, **attrs)


_markdown_renderer = mistune.Markdown(renderer=HighlightRenderer(), plugins=[table])


def render_markdown(text: str) -> str:
    """
    Render unsafe markdown from user input, returning sanitized html
    """

    converted = _markdown_renderer(text)

    # wrap in a containing tag for any additional styling
    cleaned = '<div class="markdown">' + converted.strip() + "</div>"
    return cleaned


def render_db_fields_to_html(*fields: InstrumentedAttribute) -> None:
    """Create event listener to render markdown to HTML for fields on a model"""

    def _before_update_event_listener(
        mapper: Mapper[_O], connection: Connection, target: _O
    ) -> None:
        for field in fields:
            html = render_markdown(markdown) if (markdown := getattr(target, field)) else None
            setattr(target, field + "_html", html)

    return _before_update_event_listener
