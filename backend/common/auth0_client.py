"""
Auth0 client for the email OTP flow.

Wraps the three Auth0 calls the email flow needs:

- ``start_passwordless`` — POST /passwordless/start (send OTP code)
- ``exchange_otp``       — POST /oauth/token with the passwordless OTP grant,
                           verifying the returned ID token signature against the
                           tenant JWKS before trusting its claims
- ``delete_user``        — DELETE /api/v2/users/{sub} via the Management API,
                           so unlinking a sign-in also removes its Auth0 user
                           (and the sessions/refresh tokens hanging off it)

Auth0 users are never merged or mutated: every sign-in method stays its own
Auth0 user, and the ``user_identities`` table is the only thing mapping those
subs to one Purrf account. Deletion is the one Management API write left — the
M2M app therefore only needs the ``delete:users`` scope.

Auth0 HTTP failures are translated into the shared domain exceptions so the API
layer can answer callers correctly: a throttled tenant becomes
``RateLimitedError`` (429) and a wrong/expired code becomes ``ValueError`` (400)
rather than a blanket 503.
"""

import os
import time
import urllib.parse
from http import HTTPStatus

import jwt
import requests
from jwt import PyJWKClient

from backend.common.environment_constants import (
    AUTH0_M2M_AUDIENCE,
    AUTH0_M2M_CLIENT_ID,
    AUTH0_M2M_CLIENT_SECRET,
    AUTH0_PASSWORDLESS_CLIENT_ID,
    AUTH0_PASSWORDLESS_CLIENT_SECRET,
    AUTH0_TENANT_DOMAIN,
)
from backend.common.exceptions import RateLimitedError

_PASSWORDLESS_GRANT_TYPE = "http://auth0.com/oauth/grant-type/passwordless/otp"
_CLIENT_CREDENTIALS_GRANT_TYPE = "client_credentials"
_HTTP_TIMEOUT_SECONDS = 10
_ID_TOKEN_ALGORITHMS = ["RS256"]
_M2M_TOKEN_REFRESH_BUFFER_SECONDS = 60


class Auth0Client:
    def __init__(self, logger):
        """
        Initialize the Auth0Client, reading the tenant and credentials from the
        environment.

        Args:
            logger: Application logger.
        """
        self._tenant = os.getenv(AUTH0_TENANT_DOMAIN)
        self._pwl_client_id = os.getenv(AUTH0_PASSWORDLESS_CLIENT_ID)
        self._pwl_client_secret = os.getenv(AUTH0_PASSWORDLESS_CLIENT_SECRET)
        self._m2m_client_id = os.getenv(AUTH0_M2M_CLIENT_ID)
        self._m2m_client_secret = os.getenv(AUTH0_M2M_CLIENT_SECRET)
        self._m2m_audience = os.getenv(AUTH0_M2M_AUDIENCE)
        self._m2m_token_cache = None  # {"access_token": str, "expires_at": float}
        self._issuer = f"https://{self._tenant}/"
        # PyJWKClient fetches and caches the tenant signing keys lazily on first
        # verification, so constructing it here makes no network call.
        self._jwks_client = PyJWKClient(f"https://{self._tenant}/.well-known/jwks.json")
        self._logger = logger

    def start_passwordless(self, email: str) -> None:
        """
        Trigger Auth0 to email a one-time code to `email`.

        Args:
            email (str): Address to send the passwordless OTP code to.

        Raises:
            RateLimitedError: If Auth0 throttles the tenant (HTTP 429).
            RuntimeError: For any other non-2xx Auth0 response.
        """
        url = f"https://{self._tenant}/passwordless/start"
        payload = {
            "client_id": self._pwl_client_id,
            "client_secret": self._pwl_client_secret,
            "connection": "email",
            "email": email,
            "send": "code",
        }
        response = requests.post(url, json=payload, timeout=_HTTP_TIMEOUT_SECONDS)
        self._raise_for_auth0_error(response, "start_passwordless")
        self._logger.info(
            "[Auth0Client] start_passwordless sent code to %s", _mask_email(email)
        )

    def exchange_otp(self, email: str, otp: str) -> dict:
        """
        Submit the OTP and return the verified ID token claims.

        The ID token signature is verified against the tenant JWKS (audience =
        passwordless client, issuer = tenant) before any claim is trusted.

        Args:
            email (str): Address the OTP was sent to (the passwordless username).
            otp (str): The one-time code the user entered.

        Returns:
            dict: The verified ID token claims (e.g. sub, email, email_verified).

        Raises:
            RateLimitedError: If Auth0 throttles the request (HTTP 429).
            ValueError: If the code is wrong or expired (Auth0 invalid_grant), or
                the returned ID token fails verification.
            RuntimeError: For any other Auth0 failure.
        """
        url = f"https://{self._tenant}/oauth/token"
        payload = {
            "grant_type": _PASSWORDLESS_GRANT_TYPE,
            "client_id": self._pwl_client_id,
            "client_secret": self._pwl_client_secret,
            "username": email,
            "otp": otp,
            "realm": "email",
            "scope": "openid email",
        }
        response = requests.post(url, json=payload, timeout=_HTTP_TIMEOUT_SECONDS)

        if not response.ok:
            error, description = _auth0_error(response)
            # Log Auth0's raw reason server-side; raised messages stay high-level
            # so the API never echoes Auth0 internals back to the caller.
            self._logger.warning(
                "[Auth0Client] Auth0 exchange_otp failed: status=%s error=%s detail=%s",
                response.status_code,
                error,
                description,
            )
            if HTTPStatus.TOO_MANY_REQUESTS == response.status_code:
                raise RateLimitedError(
                    "Too many verification attempts; try again later"
                )
            # invalid_grant is Auth0's signal for a wrong/expired OTP.
            if error == "invalid_grant":
                raise ValueError("Incorrect or expired verification code")
            raise RuntimeError("Email verification failed")

        id_token = response.json()["id_token"]
        claims = self._verify_id_token(id_token)
        self._logger.info(
            "[Auth0Client] exchange_otp verified sub=%s email_verified=%s",
            claims.get("sub"),
            claims.get("email_verified"),
        )
        return claims

    def delete_user(self, sub: str) -> None:
        """
        Delete the Auth0 user identified by ``sub`` via the Management API.

        Called when a sign-in identity is unlinked: each sign-in method is its
        own Auth0 user, so once its ``user_identities`` row is gone the Auth0
        user (and any sessions/refresh tokens on it) must not outlive it. A 404
        is treated as success so a retry after a partial failure is idempotent.

        Args:
            sub (str): The Auth0 user_id to delete (e.g. ``email|abc123``).

        Raises:
            RateLimitedError: If Auth0 throttles the request (HTTP 429).
            RuntimeError: For any other non-2xx Auth0 response.
        """
        encoded = urllib.parse.quote(sub, safe="")
        url = f"https://{self._tenant}/api/v2/users/{encoded}"
        response = requests.delete(
            url,
            headers={"Authorization": f"Bearer {self._get_m2m_token()}"},
            timeout=_HTTP_TIMEOUT_SECONDS,
        )

        if response.status_code == HTTPStatus.NOT_FOUND:
            self._logger.info(
                "[Auth0Client] delete_user idempotent: %s already gone", sub
            )
            return
        self._raise_for_auth0_error(response, "delete_user")
        self._logger.info("[Auth0Client] delete_user removed %s", sub)

    def _get_m2m_token(self) -> str:
        """
        Return a cached Management API M2M access token, refreshing if near expiry.

        The token is reused until it falls within the refresh buffer of its
        expiry, so the Management API calls share one client-credentials grant.

        Returns:
            str: A valid Management API access token.

        Raises:
            RateLimitedError: If Auth0 throttles the token request (HTTP 429).
            RuntimeError: For any other non-2xx Auth0 response.
        """
        now = time.time()
        cache = self._m2m_token_cache
        if cache and cache["expires_at"] - _M2M_TOKEN_REFRESH_BUFFER_SECONDS > now:
            return cache["access_token"]

        url = f"https://{self._tenant}/oauth/token"
        payload = {
            "grant_type": _CLIENT_CREDENTIALS_GRANT_TYPE,
            "client_id": self._m2m_client_id,
            "client_secret": self._m2m_client_secret,
            "audience": self._m2m_audience,
        }
        response = requests.post(url, json=payload, timeout=_HTTP_TIMEOUT_SECONDS)
        self._raise_for_auth0_error(response, "get_m2m_token")
        body = response.json()
        expires_in = body.get("expires_in", 3600)
        self._m2m_token_cache = {
            "access_token": body["access_token"],
            "expires_at": now + expires_in,
        }
        return body["access_token"]

    def _verify_id_token(self, id_token: str) -> dict:
        """
        Verify the ID token against the tenant JWKS and return its claims.

        Checks signature, audience (passwordless client), and issuer (tenant).

        Args:
            id_token (str): The raw JWT ID token returned by the OTP exchange.

        Returns:
            dict: The decoded, verified token claims.

        Raises:
            ValueError: If signature, audience, issuer, or expiry verification fails.
        """
        try:
            signing_key = self._jwks_client.get_signing_key_from_jwt(id_token)
            return jwt.decode(
                id_token,
                signing_key.key,
                algorithms=_ID_TOKEN_ALGORITHMS,
                audience=self._pwl_client_id,
                issuer=self._issuer,
            )
        except jwt.PyJWTError as e:
            raise ValueError(f"Auth0 ID token verification failed: {e}")

    def _raise_for_auth0_error(self, response, op: str) -> None:
        """
        Translate a non-2xx Auth0 response into the right domain exception.

        Auth0's raw reason is logged server-side; the raised exception carries
        only a high-level message, so the API response never leaks Auth0
        internals to the caller.

        Args:
            response (requests.Response): The Auth0 HTTP response to inspect.
            op (str): Short operation name used in the log line and error message.

        Raises:
            RateLimitedError: If the response is HTTP 429.
            RuntimeError: For any other non-2xx response. A 2xx response is a no-op.
        """
        if response.ok:
            return
        error, description = _auth0_error(response)
        self._logger.error(
            "[Auth0Client] Auth0 %s failed: status=%s error=%s detail=%s",
            op,
            response.status_code,
            error,
            description,
        )
        if response.status_code == HTTPStatus.TOO_MANY_REQUESTS:
            raise RateLimitedError("Auth0 rate limit reached; try again later")
        raise RuntimeError(f"Auth0 {op} failed")


def _auth0_error(response) -> tuple[str | None, str | None]:
    """
    Extract Auth0's ``(error, description)`` pair from a failed response body.

    Args:
        response (requests.Response): The failed Auth0 HTTP response.

    Returns:
        tuple[str | None, str | None]: The ``(error, description)`` pair, with
        either element None when the body is not JSON or omits the field.
    """
    try:
        body = response.json()
    except ValueError:
        return None, None
    description = (
        body.get("error_description") or body.get("message") or body.get("error")
    )
    return body.get("error"), description


def _mask_email(email: str) -> str:
    """
    Mask the local part of an email for safe logging (e.g. 'a***e@x.com').

    Args:
        email (str): The email address to mask.

    Returns:
        str: The address with its local part masked, or the input unchanged if
        it is empty or has no '@'.
    """
    if not email or "@" not in email:
        return email
    local, _, domain = email.partition("@")
    if len(local) <= 2:
        masked_local = "*" * len(local)
    else:
        masked_local = local[0] + "*" * (len(local) - 2) + local[-1]
    return f"{masked_local}@{domain}"
