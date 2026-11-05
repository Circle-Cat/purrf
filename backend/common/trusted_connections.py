"""Connection allowlist for trusting an IdP's email assertion.

A sign-in's email claim counts as first-party proof of mailbox control only
when the connection is allowlisted here AND the IdP reports the address
verified. 'email|' is Auth0 passwordless — the login itself is the OTP
round-trip, live and always valid regardless of domain. 'google-oauth2|' is
Google, the mailbox authority for gmail and domain-verified Workspace
addresses — but only when the address's mail is actually Google-hosted. For a
domain whose mail is NOT Google-hosted, Google's email_verified is a
one-time historical claim (true the moment the consumer Google account was
created, or the domain last pointed at Google) that never expires and never
gets re-checked; a stale consumer Google account can keep asserting
verification for an address whose mail has long since moved elsewhere. This
is the LinkedIn-equivalent posture and, for ordinary third-party domains, the
residual risk is ACCEPTED. `_GOOGLE_STALE_VERIFICATION_DOMAINS` carves out
the one known corp-sensitive exception: `u.circlecat.org` is Microsoft-hosted
mail, so a Google assertion for it is never live proof and must not route
into the employee account. Everything else is default-deny: an unlisted
connection's email claim proves nothing, no matter what email_verified
says — this list is the single trust boundary, so widening it or shrinking
the exclusion list is a security decision, not a refactor.
"""

_TRUSTED_SUB_PREFIXES = ("email|", "google-oauth2|")

# Domains whose mail is Microsoft-hosted (not Google), so a google-oauth2|
# email_verified claim for them is a stale, never-expiring historical proof
# rather than a live mailbox check. These logins must go through the OTP
# bridge instead of being trusted outright.
_GOOGLE_STALE_VERIFICATION_DOMAINS = ("u.circlecat.org",)


def is_trusted_email_assertion(sub: str, email_verified: bool, email: str) -> bool:
    """Whether this login's email claim counts as first-party mailbox proof.

    Args:
        sub (str): Auth0 subject identifier, shaped ``connection|id``.
        email_verified (bool): The IdP's email_verified claim for the login.
        email (str): The login's claimed address, used to check the
            google-oauth2 stale-verification domain exclusion.

    Returns:
        bool: True only for an allowlisted connection asserting a verified
        address; False for everything else (default-deny), including a
        google-oauth2 assertion for a known non-Google-hosted-mail domain.
    """
    if not email_verified or not sub.startswith(_TRUSTED_SUB_PREFIXES):
        return False
    if sub.startswith("google-oauth2|"):
        domain = email.rsplit("@", 1)[-1].lower()
        if domain in _GOOGLE_STALE_VERIFICATION_DOMAINS:
            return False
    return True
