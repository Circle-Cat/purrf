from enum import StrEnum


class IdentityType(StrEnum):
    """
    Identity source bucket on UserContextDto / user_identities.identity_type,
    set by the auth layer.

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

    Only an EXTERNAL passwordless login is row-less. A passwordless ('email|')
    sub merely proves control of a mailbox; the confirmed user_emails row is
    the identity anchor, so the login is resolved by confirmed address on every
    request and never recorded as a sub. A corp (INTERNAL) passwordless login
    still records an identity row — internal classification is derived from the
    presence of an INTERNAL identity row — and google logins are durable
    third-party credentials that stay sub-routed. ``identity_type`` may be an
    ``IdentityType`` member or its string value; both compare equal (StrEnum).
    """
    return sub.startswith(_PASSWORDLESS_SUB_PREFIX) and (
        identity_type == IdentityType.EXTERNAL
    )
