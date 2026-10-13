"""Plain text and HTML forms of an email body."""

import html
import re
from html import unescape

# An anchor carrying an href, captured as (href, label). A link's URL lives in
# the tag, not between the tags, so the plain-text form has to pull it out
# before markup is stripped or it is lost with the tag.
_ANCHOR_RE = re.compile(
    r'(?is)<a\b[^>]*?\bhref\s*=\s*["\']([^"\']*)["\'][^>]*>(.*?)</a\s*>'
)
_TAG_RE = re.compile(r"<[^>]+>")


def _expand_link(match):
    """
    Render one anchor as ``label (url)`` for the plain-text form.

    The url is kept whenever there is one, so a link never reaches a
    plain-text reader as unclickable prose. It is only left out when the
    label already *is* the url, where repeating it would read as
    ``https://x (https://x)``; a ``mailto:`` scheme is likewise dropped when
    the label is the bare address.
    """
    href = match.group(1).strip()
    label = _TAG_RE.sub("", match.group(2)).strip()
    if not href:
        return label
    if not label:
        return href
    bare = unescape(href).removeprefix("mailto:")
    if unescape(label).rstrip("/") in (
        unescape(href).rstrip("/"),
        bare.rstrip("/"),
    ):
        return label
    return f"{label} ({href})"


def html_to_text(body: str) -> str:
    """Derive readable plain text from an HTML body.

    Args:
        body (str): HTML.

    Returns:
        str: The text, links as ``label (url)``, blank-line runs collapsed.
    """
    text = re.sub(r"(?i)<br\s*/?>", "\n", body)
    text = re.sub(r"(?i)</p\s*>", "\n\n", text)
    text = re.sub(r"(?i)<li[^>]*>", "\n- ", text)
    text = re.sub(r"(?i)</(h[1-6]|div|ul|ol)\s*>", "\n", text)
    # Must run before the tag strip below, which would take the href with it.
    text = _ANCHOR_RE.sub(_expand_link, text)
    text = _TAG_RE.sub("", text)
    text = unescape(text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def text_to_html(text: str) -> str:
    """Escape plain text into an HTML body, one ``<br>`` per line break.

    The body sits in a ``pre-wrap`` div so typed indentation and runs of
    spaces survive; the lines are joined by ``<br>`` alone, so a newline
    still reads back as one newline.

    Args:
        text (str): What the sender typed.

    Returns:
        str: HTML that shows exactly that text; nothing in it is markup.
    """
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    inner = "<br>".join(html.escape(line) for line in lines)
    return f'<div style="white-space:pre-wrap">{inner}</div>'
