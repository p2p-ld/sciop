import bleach
import mistune
from mistune.plugins.table import table
from pygments import highlight
from pygments.formatters import html
from pygments.lexers import get_lexer_by_name

ALLOWED_TAGS = (bleach.sanitizer.ALLOWED_TAGS - {"a"}) | {
    "h1",
    "h2",
    "h3",
    "h4",
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


class HighlightRenderer(mistune.HTMLRenderer):
    """
    References:
        https://github.com/lepture/mistune/issues/54#issuecomment-557503350
    """

    def block_code(self, code: str, lang: str) -> str:
        if not lang:
            return "\n<pre><code>%s</code></pre>\n" % mistune.escape(code)
        lexer = get_lexer_by_name(lang, stripall=True)
        formatter = html.HtmlFormatter(lineseparator="<br>")
        return highlight(code, lexer, formatter)


def _get_renderer() -> mistune.Markdown:
    """instantiate the mistune markdown renderer with plugins"""
    renderer = HighlightRenderer()
    markdown = mistune.Markdown(renderer=renderer, plugins=[table])

    return markdown


def _sanitize_html(text: str) -> str:
    """
    bleach sanitization with some added stuff to allow for syntax highlighting

    Allows additional tags:
    - only allows the first four levels of h2's to avoid going over 6 total on the page
      https://adrianroselli.com/2024/05/level-setting-heading-levels.html
    - table elements
    - p
    - span
    - details/summary

    References:
        https://bleach.readthedocs.io/en/latest/clean.html#bleach.clean
    """

    cleaned = bleach.clean(text, tags=ALLOWED_TAGS)
    return cleaned


def render_markdown(text: str) -> str:
    """
    Render unsafe markdown from user input, returning sanitized html
    """
    renderer = _get_renderer()
    converted = renderer(text)
    cleaned = _sanitize_html(converted)

    # wrap in a containing tag for any additional styling
    cleaned = '<div class="markdown">' + cleaned + "</div>"
    return cleaned
