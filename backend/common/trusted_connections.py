"""Connection allowlist for trusting an IdP's email assertion.

A sign-in's email claim counts as first-party proof of mailbox control only
when the connection is allowlisted here AND the IdP reports the address
verified. 'email|' is Auth0 passwordless — the login itself is the OTP
round-trip. 'google-oauth2|' is Google, the mailbox authority for gmail and
domain-verified Workspace addresses. Everything else is default-deny: an
unlisted connection's email claim proves nothing, no matter what
email_verified says — this list is the single trust boundary, so widening
it is a security decision, not a refactor.
"""

_TRUSTED_SUB_PREFIXES = ("email|", "google-oauth2|")


def is_trusted_email_assertion(sub: str, email_verified: bool) -> bool:
    """Whether this login's email claim counts as first-party mailbox proof.

    Args:
        sub (str): Auth0 subject identifier, shaped ``connection|id``.
        email_verified (bool): The IdP's email_verified claim for the login.

    Returns:
        bool: True only for an allowlisted connection asserting a verified
        address; False for everything else (default-deny).
    """
    return bool(email_verified) and sub.startswith(_TRUSTED_SUB_PREFIXES)
