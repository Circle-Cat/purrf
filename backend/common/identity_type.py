from enum import StrEnum


class IdentityType(StrEnum):
    """
    Identity source bucket on UserContextDto, set by the auth layer
    (per-request, domain-derived; no longer persisted on user_identities).

    EXTERNAL  - default for Cloudflare-authenticated users
    CRONJOB   - Google service accounts; the middleware skips first-login
                bootstrap for these
    INTERNAL  - Circle Cat employees (Google Workspace @circlecat.org)
    """

    EXTERNAL = "external"
    CRONJOB = "cronjob"
    INTERNAL = "internal"


_PASSWORDLESS_SUB_PREFIX = "email|"


def is_rowless_login(sub: str, identity_type) -> bool:
    """Whether this login leaves NO row in user_identities.

    Every passwordless ('email|') login is now row-less — internal and
    external alike. A passwordless sub merely proves control of a mailbox;
    the confirmed user_emails row is the anchor, and internal classification
    lives on the ``users.is_internal`` state column, so no passwordless login
    is recorded as a sub. Google / social subs are durable third-party
    credentials that stay sub-routed. ``identity_type`` is accepted for
    call-site compatibility but no longer affects the result.
    """
    return sub.startswith(_PASSWORDLESS_SUB_PREFIX)
