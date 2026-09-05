"""The signed token that stands in for a session on the content origin.

Course files are served from a hostname with no Access application and no
cookie, so this signature is the only thing between a URL and somebody else's
course. It is deliberately small: who, which assignment, when the session was
minted, and when it stops working.

It names the package by id, never by storage prefix. A prefix baked into a
token would keep pointing at files the replacement cleanup is about to delete;
an id is resolved against the database on every request, so the prefix behind
it can move without the token meaning anything different.

Naming the package at all is what binds a run to the thing it is actually
running. A tab left open across a replacement holds a token for a package that
no longer exists, so every answer it gets -- files, and the progress it posts
back -- is refused rather than quietly served or stored against its successor.
Without that binding, the tab's in-memory CMI model gets written back over the
resume state the replacement just cleared, and the learner reopens onto a
bookmark that names a lesson the new package does not have.
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
    """Who this token is for, which assignment, and which package it runs."""

    training_id: int
    user_id: int
    expires_at: int
    # The package this run opened against, by id. Not its storage prefix --
    # that is read fresh per request -- but enough to refuse a run whose
    # package has since been replaced, and to land a verification stamp on
    # the package that was actually run rather than on whatever is live now.
    package_id: int


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
    *,
    package_id: int,
    now: int | None = None,
    lifetime_seconds: int = TOKEN_LIFETIME_SECONDS,
) -> tuple[str, int]:
    """Sign a token for one person's run of one package.

    ``package_id`` is keyword-only: it joined three parameters that are all
    plain ints, where a silently mis-ordered call would mint a token naming
    the wrong package and be caught by nothing.

    Args:
        signing_key (str): TRAINING_TOKEN_SIGNING_KEY.
        training_id (int): The assignment being opened.
        user_id (int): Who is opening it.
        package_id (int): The package this run opens against.
        now (int | None): Unix seconds, for tests.
        lifetime_seconds (int): How long the token lasts.

    Returns:
        tuple[str, int]: The token, and its expiry as unix seconds.

    Raises:
        ValueError: No signing key configured.
    """
    if not signing_key:
        # Which variable is missing is logged by the caller, which has a
        # logger; this message reaches a browser.
        raise ValueError("Training content is not available.")
    expires_at = int(now if now is not None else time.time()) + lifetime_seconds
    payload = json.dumps(
        {"p": package_id, "t": training_id, "u": user_id, "e": expires_at},
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    encoded = _b64encode(payload)
    return f"{encoded}.{_signature(signing_key, payload)}", expires_at


def _authentic_claims(signing_key: str, token: str) -> ContentTokenClaims:
    """Read a token's claims once its signature is proven, expiry aside.

    Raises:
        InvalidContentToken: Malformed or altered.
        ValueError: No signing key configured.
    """
    if not signing_key:
        raise ValueError("Training content is not available.")

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
        package_id = int(claims["p"])
    except (ValueError, KeyError, TypeError) as error:
        raise InvalidContentToken("Malformed content token.") from error

    return ContentTokenClaims(
        training_id=training_id,
        user_id=user_id,
        expires_at=expires_at,
        package_id=package_id,
    )


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
    claims = _authentic_claims(signing_key, token)
    if claims.expires_at <= int(now if now is not None else time.time()):
        raise InvalidContentToken("Content token has expired.")
    return claims


def read_session_package(signing_key: str, token: str) -> int:
    """Which package the run in the tab holding this token is running.

    Expiry is not consulted. Here the token is not the credential -- the
    caller reached the app origin with its own Access identity -- and the one
    question is which package that tab opened against. A twelve-hour sitting
    that overran its token still answers it, and refusing one would cost the
    longest run its last save.

    Args:
        signing_key (str): TRAINING_TOKEN_SIGNING_KEY.
        token (str): The token the page was given when it opened the course.

    Returns:
        int: The package the run opened against.

    Raises:
        InvalidContentToken: Malformed, altered, or of the payload shape that
            predates packages carrying an id.
        ValueError: No signing key configured.
    """
    return _authentic_claims(signing_key, token).package_id
