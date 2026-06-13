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
