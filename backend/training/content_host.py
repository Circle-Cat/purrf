"""Checking at startup that course files are not served from the app's origin.

The whole safety of the content route rests on one thing nothing asserted: the
hostname in TRAINING_CONTENT_HOST is not a hostname the app itself answers on.
Set the two equal and everything still works -- /p/ becomes an unauthenticated
path on the API origin, the content route answers there, and third-party course
JavaScript ends up same-origin with the API and with a deliberately JS-readable
Cloudflare Access cookie. Nothing fails, so nobody finds out.

The backend is not told its own hostname anywhere else, so the origins it
answers on are named explicitly in APP_ORIGINS, and this refuses to start when
content hosting is configured without them.
"""

from urllib.parse import urlsplit


def hostname_of(origin: str) -> str:
    """The bare, lowercased hostname in an origin.

    Accepts either a full origin (``https://purrf.io``) or a bare hostname,
    and drops any port or path, so an operator writing either form gets the
    same comparison.

    Args:
        origin (str): An origin or hostname.

    Returns:
        str: The hostname, or ``""`` if there is none.
    """
    candidate = origin.strip()
    if not candidate:
        return ""
    if "//" not in candidate:
        candidate = f"//{candidate}"
    return urlsplit(candidate).hostname or ""


def assert_content_host_isolated(content_host, app_origins) -> None:
    """Refuse to start with a content host the app also answers on.

    Args:
        content_host (str | None): TRAINING_CONTENT_HOST. Absent means content
            hosting is not configured, which the route and the middleware
            exemption both already fail closed on, so there is nothing to check.
        app_origins (str | None): APP_ORIGINS, comma-separated.

    Raises:
        ValueError: The content host is not a bare hostname, the app's own
            origins are unknown, or the two name the same host.
    """
    if not content_host:
        return

    # Compared against the Host header exactly, so a value carrying a scheme,
    # a port or a path matches nothing: content would 404 everywhere while the
    # middleware exemption quietly stopped applying. That is a startup failure,
    # not something to normalise away.
    if content_host != content_host.strip().lower() or any(
        character in content_host for character in " \t/:"
    ):
        raise ValueError(
            "TRAINING_CONTENT_HOST must be a bare lowercase hostname "
            f"(no scheme, port or path); got {content_host!r}."
        )

    app_hostnames = {
        hostname_of(origin) for origin in (app_origins or "").split(",")
    } - {""}
    if not app_hostnames:
        raise ValueError(
            "TRAINING_CONTENT_HOST is set but APP_ORIGINS is not, so the "
            "content host cannot be checked against the app's own origins. "
            "Set APP_ORIGINS to every origin this app answers on, "
            "comma-separated."
        )

    if content_host in app_hostnames:
        raise ValueError(
            f"TRAINING_CONTENT_HOST ({content_host}) is one of APP_ORIGINS. "
            "Course files must be served from their own hostname, or course "
            "JavaScript runs same-origin with the API and the Access cookie."
        )
