from functools import partial
from textwrap import dedent

import pytest
from bs4 import BeautifulSoup

from sciop.services.markdown import render_markdown

bs = partial(BeautifulSoup, features="html.parser")


@pytest.mark.parametrize(
    "text,expected_html",
    [
        ("", ""),
        ("Hello, World!", "<p>Hello, World!</p>"),
        ("# Heading 1", "<h1>Heading 1</h1>"),
        ("## Heading 2", "<h2>Heading 2</h2>"),
        ("### Heading 3", "<h3>Heading 3</h3>"),
        ("#### Heading 4", "<h4>Heading 4</h4>"),
        ("##### Heading 5", "<strong>Heading 5</strong>"),
        ("<h1>Heading 1</h1>", "<h1>Heading 1</h1>"),
        ("<h2>Heading 2</h2>", "<h2>Heading 2</h2>"),
        ("<h3>Heading 3</h3>", "<h3>Heading 3</h3>"),
        ("<h4>Heading 4</h4>", "<h4>Heading 4</h4>"),
        ("<h5>Heading 5</h5>", "&lt;h5&gt;Heading 5&lt;/h5&gt;"),
        (
            dedent(
                """\
                    | Header 1 | Header 2 |
                    |----------|----------|
                    | Cell 1   | Cell 2   |
                """
            ),
            bs(
                """
                <table>
                <thead><tr> <th>Header 1 </th> <th>Header 2 </th></tr> </thead>
                <tbody><tr> <td>Cell 1 </td> <td>Cell 2 </td></tr> </tbody>
                </table>
                """
            ),
        ),
        (
            dedent(
                """\
                    * foo
                    * bar
                """
            ),
            bs("<ul><li>foo</li><li>bar</li></ul>"),
        ),
        (
            dedent(
                """\
                ```
                def hello():
                    print("Hello, World!")
                ```
                """
            ),
            "<pre><code>def hello():\n    print(&quot;Hello, World!&quot;)\n</code></pre>",
        ),
        (
            dedent(
                """\
                ```python
                def hello():
                    print("Hello, World!")
                ```
                """
            ),
            bs(
                '<div class="highlight">'
                '<pre><span></span><span class="k">def</span><span class="w"> </span>'
                '<span class="nf">hello</span><span class="p">():</span>\n'
                '    <span class="nb">print</span><span class="p">(</span>'
                '<span class="s2">&quot;Hello, World!&quot;</span><span class="p">)</span>\n'
                "</pre></div>"
            ),
        ),
        (
            dedent(
                """\
                    <details>
                    <summary>Blueprints</summary>
                    <p>Here are all the blueprints</p>
                    </details>
                """
            ),
            bs(
                """\
                    <details>
                    <summary>Blueprints</summary>
                    <p>Here are all the blueprints</p>
                    </details>
                """
            ),
        ),
        (
            dedent(
                """\
                    This is a *markdown* description
                    
                    And it does markdown things
                    
                    <details>
                    <summary>whats up this is a summary tag</summary>
                    
                    ## Markdown in details
                    
                    ```python
                    a = 1 + 1
                    ```
                    
                    </details>
                """
            ),
            bs(
                "<p>This is a <em>markdown</em> description</p>"
                "<p>And it does markdown things</p>"
                "<details>"
                "<summary>whats up this is a summary tag</summary>"
                "<h2>Markdown in details</h2>"
                '<div class="highlight"><pre><span></span><span class="n">a</span> '
                '<span class="o">=</span> <span class="mi">1</span> <span class="o">+</span> '
                '<span class="mi">1</span>\n'
                "</pre></div>"
                "</details>"
            ),
        ),
    ],
    ids=[
        "empty",
        "text",
        "heading1",
        "heading2",
        "heading3",
        "heading4",
        "heading5",
        "heading1_html",
        "heading2_html",
        "heading3_html",
        "heading4_html",
        "heading5_html",
        "table",
        "unordered_list",
        "code_block",
        "python_code_block",
        "details",
        "details_markdown",
    ],
)
def test_render_markdown(text: str, expected_html: str | BeautifulSoup) -> None:
    """We can render markdown, including syntax highlighting"""
    wrapped_html = render_markdown(text)
    assert wrapped_html.startswith('<div class="markdown">')
    assert wrapped_html.endswith("</div>")
    html = wrapped_html[22:-6]
    if isinstance(expected_html, str):
        # strict equivalency for raw strings
        assert html == expected_html
    else:
        # parse and prettify via BS so that whitespace differences don't matter
        html = bs(html)
        assert html.prettify() == expected_html.prettify()


@pytest.mark.parametrize(
    "text,expected_html",
    [
        (
            "<script>window.alert('hey');</script>",
            "&lt;script&gt;window.alert('hey');&lt;/script&gt;",
        ),
        (
            "<div style=\"background: url('https://example.com/tracker.gif');\">hey</div>",
            "<div>hey</div>",
        ),
        (
            "<img src='https://example.com/tracker.gif'></img>",
            "<p>&lt;img src='https://example.com/tracker.gif'&gt;&lt;/img&gt;</p>",
        ),
    ],
)
def test_sanitize_markdown(text: str, expected_html: str | BeautifulSoup) -> None:
    """Scripts and other xss vectors are removed from user input"""
    wrapped_html = render_markdown(text)
    assert wrapped_html.startswith('<div class="markdown">')
    assert wrapped_html.endswith("</div>")
    html = wrapped_html[22:-6]
    if isinstance(expected_html, str):
        # strict equivalency for raw strings
        assert html == expected_html
    else:
        # parse and prettify via BS so that whitespace differences don't matter
        html = bs(html)
        assert html.prettify() == expected_html.prettify()
