"""A stored email attachment as an HTTP download that cannot name a path."""

from urllib.parse import quote

from fastapi import Response

_UNSAFE_IN_NAME = frozenset('/\\"')


def attachment_disposition(name: str) -> str:
    """A ``Content-Disposition`` that downloads ``name`` and cannot name a path.

    Path separators, quotes and control characters are dropped, as are
    leading dots and spaces. The quoted ``filename`` is an ASCII stand-in;
    ``filename*`` (RFC 5987) carries the real name.

    Args:
        name (str): The file name as the sender wrote it.

    Returns:
        str: The header value.
    """
    cleaned = "".join(
        c for c in name if c not in _UNSAFE_IN_NAME and ord(c) >= 32 and ord(c) != 127
    ).lstrip(". ")
    cleaned = cleaned or "attachment"
    ascii_name = "".join(c if c.isascii() else "_" for c in cleaned)
    return (
        f'attachment; filename="{ascii_name}"; '
        f"filename*=UTF-8''{quote(cleaned, safe='')}"
    )


def attachment_response(content: bytes, name: str) -> Response:
    """The attachment as a download the browser will not try to render.

    Args:
        content (bytes): The file.
        name (str): The file name as the sender wrote it.

    Returns:
        Response: ``application/octet-stream`` with a safe disposition.
    """
    return Response(
        content=content,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": attachment_disposition(name),
            "X-Content-Type-Options": "nosniff",
        },
    )
