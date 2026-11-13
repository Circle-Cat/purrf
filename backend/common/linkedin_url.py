import re
from urllib.parse import urlsplit

_HAS_SCHEME = re.compile(r"^[a-z][a-z0-9+.-]*:", re.IGNORECASE)


def normalize_linkedin_profile_url(url: str | None) -> str | None:
    """Return `url` as a safe http(s) linkedin.com link, or None.

    Shared links end up in another user's `<a href>`, so a `javascript:` or
    `data:` URL that merely mentions linkedin.com must not pass. A link with
    no scheme ("linkedin.com/in/me") is upgraded to https, matching how the
    profile page renders it.

    Args:
        url (str | None): The untrusted link.

    Returns:
        str | None: The trimmed link (https added when it had no scheme) if
            its host is linkedin.com or *.linkedin.com, else None.
    """
    if not url or not url.strip():
        return None
    candidate = url.strip()
    if not _HAS_SCHEME.match(candidate):
        candidate = f"https://{candidate}"
    try:
        parts = urlsplit(candidate)
        host = (parts.hostname or "").lower()
    except ValueError:
        return None
    if parts.scheme.lower() not in ("http", "https"):
        return None
    if host != "linkedin.com" and not host.endswith(".linkedin.com"):
        return None
    return candidate
