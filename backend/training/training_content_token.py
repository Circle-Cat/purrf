"""The signed token that stands in for a session on the content origin.

Course files are served from a hostname with no Access application and no
cookie, so this signature is the only thing between a URL and somebody else's
course. It is deliberately small: three fields and an expiry.

It does NOT carry the storage prefix. A token outlives an upload, and a prefix
baked into one would keep pointing at files that the overwrite cleanup is about
to delete -- the learner's page would start 404ing mid-session. The prefix is
read from the database on every request instead, which is also what makes
"everybody sees the new package immediately" true.
"""

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass

# Long enough that it cannot expire in the middle of a sitting. Relative asset
# requests inherit the token from the page URL, so an expiry mid-course stops
# images and audio loading rather than prompting a re-login.
TOKEN_LIFETIME_SECONDS = 12 * 60 * 60


class InvalidContentToken(ValueError):
    """The token is malformed, altered, or past its expiry."""


@dataclass(frozen=True)
class ContentTokenClaims:
    """Who this token is for, and which assignment."""

    training_id: int
    user_id: int
    expires_at: int


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _signature(signing_key: str, payload: bytes) -> str:
    return _b64encode(
        hmac.new(signing_key.encode("utf-8"), payload, hashlib.sha256).digest()
    )


def issue_content_token(
    signing_key: str,
    training_id: int,
    user_id: int,
    now: int | None = None,
    lifetime_seconds: int = TOKEN_LIFETIME_SECONDS,
) -> tuple[str, int]:
    """Sign a token for one person's access to one assignment.

    Args:
        signing_key (str): TRAINING_TOKEN_SIGNING_KEY.
        training_id (int): The assignment being opened.
        user_id (int): Who is opening it.
        now (int | None): Unix seconds, for tests.
        lifetime_seconds (int): How long the token lasts.

    Returns:
        tuple[str, int]: The token, and its expiry as unix seconds.

    Raises:
        ValueError: No signing key configured.
    """
    if not signing_key:
        raise ValueError(
            "Training content is not configured; set TRAINING_TOKEN_SIGNING_KEY."
        )
    expires_at = int(now if now is not None else time.time()) + lifetime_seconds
    payload = json.dumps(
        {"t": training_id, "u": user_id, "e": expires_at},
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    encoded = _b64encode(payload)
    return f"{encoded}.{_signature(signing_key, payload)}", expires_at


def verify_content_token(
    signing_key: str, token: str, now: int | None = None
) -> ContentTokenClaims:
    """Check a token's signature and expiry, and read its claims.

    Args:
        signing_key (str): TRAINING_TOKEN_SIGNING_KEY.
        token (str): The token from the URL path.
        now (int | None): Unix seconds, for tests.

    Returns:
        ContentTokenClaims: What the token asserts.

    Raises:
        InvalidContentToken: Malformed, altered, or expired.
        ValueError: No signing key configured.
    """
    if not signing_key:
        raise ValueError(
            "Training content is not configured; set TRAINING_TOKEN_SIGNING_KEY."
        )

    encoded, _, provided = token.partition(".")
    if not encoded or not provided:
        raise InvalidContentToken("Malformed content token.")

    try:
        payload = _b64decode(encoded)
    except (ValueError, TypeError) as error:
        raise InvalidContentToken("Malformed content token.") from error

    # compare_digest, not ==: an ordinary comparison returns faster the earlier
    # it finds a difference, which leaks the signature a byte at a time. It
    # raises TypeError on a non-ASCII string rather than answering False, and
    # anybody can put one in a URL, so that is just another bad token.
    try:
        matches = hmac.compare_digest(_signature(signing_key, payload), provided)
    except TypeError as error:
        raise InvalidContentToken("Malformed content token.") from error
    if not matches:
        raise InvalidContentToken("Content token signature does not match.")

    try:
        claims = json.loads(payload)
        training_id = int(claims["t"])
        user_id = int(claims["u"])
        expires_at = int(claims["e"])
    except (ValueError, KeyError, TypeError) as error:
        raise InvalidContentToken("Malformed content token.") from error

    if expires_at <= int(now if now is not None else time.time()):
        raise InvalidContentToken("Content token has expired.")

    return ContentTokenClaims(
        training_id=training_id, user_id=user_id, expires_at=expires_at
    )
