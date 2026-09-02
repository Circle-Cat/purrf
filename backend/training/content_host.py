"""Deciding whether course files may be served on their own hostname at all.

The whole safety of the content route rests on one thing nothing asserted: the
hostname in TRAINING_CONTENT_HOST is not a hostname the app itself answers on.
Set the two equal and everything still works -- /p/ becomes an unauthenticated
path on the API origin, the content route answers there, and third-party course
JavaScript ends up same-origin with the API and with a deliberately JS-readable
Cloudflare Access cookie. Nothing fails, so nobody finds out.

The backend is not told its own hostname anywhere else, so the origins it
answers on are named explicitly in APP_ORIGINS. A configuration that cannot be
shown to be isolated disables content hosting and says so at error level; it
never stops the process. One optional feature that cannot verify its own
wiring must not take login, mentorship and recruiting down with it, and the
environments already carrying TRAINING_CONTENT_HOST have no APP_ORIGINS yet.

Disabled means genuinely inert, not merely logged: the resolved value is what
the auth middleware exempts on and what the content route answers on, so None
leaves /p/ authenticated like any other path and the route refusing everything.
A learner opening a course then gets an authentication failure -- visible,
rather than course files quietly served from the wrong origin.
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


def resolve_content_host(content_host, app_origins, logger) -> str | None:
    """The hostname course files may be served from, or None to serve none.

    Args:
        content_host (str | None): TRAINING_CONTENT_HOST. Absent means content
            hosting is not configured, and nothing needs deciding.
        app_origins (str | None): APP_ORIGINS, comma-separated.
        logger: Injected logger.

    Returns:
        str | None: ``content_host`` when it is provably none of the app's own
        origins, otherwise None -- which disables the middleware exemption and
        the content route together.
    """
    if not content_host:
        return None

    # Compared against the Host header exactly, so a value carrying a scheme,
    # a port or a path matches nothing: content would 404 everywhere while the
    # middleware exemption quietly stopped applying.
    if content_host != content_host.strip().lower() or any(
        character in content_host for character in " \t/:"
    ):
        logger.error(
            "[content_host] TRAINING_CONTENT_HOST (%r) is not a bare lowercase "
            "hostname; it must carry no scheme, port or path. Course content "
            "is disabled until it is corrected.",
            content_host,
        )
        return None

    app_hostnames = {
        hostname_of(origin) for origin in (app_origins or "").split(",")
    } - {""}
    if not app_hostnames:
        logger.error(
            "[content_host] TRAINING_CONTENT_HOST is set but APP_ORIGINS is "
            "missing or unreadable, so %s cannot be shown to differ from the "
            "app's own origins. Set APP_ORIGINS to every origin this app "
            "answers on, comma-separated (for example "
            "https://purrf.io,https://api.purrf.io). Course content is "
            "disabled until then.",
            content_host,
        )
        return None

    if content_host in app_hostnames:
        logger.error(
            "[content_host] TRAINING_CONTENT_HOST (%s) is one of APP_ORIGINS. "
            "Course files must be served from their own hostname, or course "
            "JavaScript runs same-origin with the API and the Access cookie. "
            "Course content is disabled until they differ.",
            content_host,
        )
        return None

    return content_host
