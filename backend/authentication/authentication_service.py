import json
import threading
from typing import Any

import jwt
import requests
from starlette.datastructures import Headers
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from jwt.algorithms import RSAAlgorithm
from backend.common.environment_constants import (
    CF_TEAM_DOMAIN,
    CF_AUD_TAG,
    GOOGLE_AUDIENCE,
    GOOGLE_SERVICE_ACCOUNT_SUBS,
)
from backend.dto.user_context_dto import UserContextDto
from backend.common.constants import is_company_email
from backend.common.identity_type import IdentityType


class AuthenticationService:
    """
    Service responsible for authenticating HTTP requests from multiple sources.

    Supports:
        1. Cloudflare Access JWTs
        2. Google Identity Tokens (for cron jobs / service accounts)

    Injects user context including roles, email, and unique identifier (sub).
    """

    def __init__(self, logger):
        """
        Initialize the AuthenticationService.

        Args:
            logger: A logger instance.
        """
        self.logger = logger
        self.cf_jwks_url = f"https://{CF_TEAM_DOMAIN}/cdn-cgi/access/certs"
        self.google_request = google_requests.Request()
        self._CF_JWKS_CACHE = {}
        # Serializes _refresh_cf_keys across threads so concurrent cache
        # misses (multiple requests after key rotation) don't all hit the
        # JWKS endpoint. authenticate_request runs inside asyncio.to_thread,
        # so the lock must be threading-level, not asyncio-level.
        self._jwks_refresh_lock = threading.Lock()

    def authenticate_request(self, headers: Headers) -> UserContextDto:
        """
        Authenticate an incoming request by automatically detecting the token source.

        The method prioritizes Cloudflare tokens first, then Google tokens. Raises
        a ValueError if no valid authentication token is found.

        Args:
            headers (Headers): The request headers containing authentication information.

        Returns:
            UserContextDto: Contains the user's sub, primary_email, and roles.
        """
        # Check Cloudflare token first
        cf_token = headers.get("Cf-Access-Jwt-Assertion") or headers.get(
            "Cf-Access-Token"
        )
        if cf_token:
            return self._verify_cloudflare(cf_token)

        # Then check Google Bearer token
        auth_header = headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            return self._verify_google(token)

        # If no token found
        raise ValueError("Missing authentication credentials")

    def _verify_cloudflare(self, token: str) -> UserContextDto:
        """
        Verify a Cloudflare Access JWT and construct the user context.

        Args:
            token (str): Cloudflare JWT token.

        Returns:
            UserContextDto: User information including roles.
        """
        signing_key = self._get_cf_signing_key(token)
        try:
            payload = jwt.decode(
                token,
                key=signing_key,
                audience=CF_AUD_TAG,
                algorithms=["RS256"],
                options={"verify_iss": True},
                issuer=f"https://{CF_TEAM_DOMAIN}",
            )
        except Exception as e:
            raise ValueError(f"Cloudflare Token Invalid: {str(e)}")

        return self._build_context(payload, source="cloudflare")

    def verify_google_token(self, token: str) -> dict[str, Any]:
        """
        Verify a Google identity token and return its claims.

        For callers that assert on the claims themselves rather than acting as
        a user -- the notification delivery route checks `sub` against the
        pusher accounts this deployment provisioned and builds no user context.

        Args:
            token (str): Google Identity token.

        Returns:
            dict[str, Any]: The verified claims.

        Raises:
            ValueError: The token is not a valid Google token for this
                audience.
        """
        try:
            return id_token.verify_token(
                token, self.google_request, audience=GOOGLE_AUDIENCE
            )
        except ValueError as e:
            raise ValueError(f"Google Token Invalid: {str(e)}")

    def _verify_google(self, token: str) -> UserContextDto:
        """
        Verify a Google identity token and construct the user context.

        The `sub` assertion cannot move up into verify_google_token: the
        notification delivery route shares it and checks its own pusher
        allowlist, so this check one level higher would reject every push.

        Args:
            token (str): Google Identity token.

        Returns:
            UserContextDto: User information including roles.

        Raises:
            ValueError: The token is not a valid Google token for this
                audience, or it was minted by a service account that is not
                allowlisted.
        """
        payload = self.verify_google_token(token)

        if not GOOGLE_SERVICE_ACCOUNT_SUBS:
            self.logger.error(
                "[AuthenticationService] GOOGLE_SERVICE_ACCOUNT_SUBS is empty, "
                "rejecting every Google token. Set it on the environment's secret."
            )
            raise ValueError("Google Token Invalid: caller not allowed")

        # Omitted from the raised message so a caller probing the endpoint
        # learns nothing about the expected value.
        sub = payload.get("sub")
        if sub not in GOOGLE_SERVICE_ACCOUNT_SUBS:
            self.logger.warning(
                "[AuthenticationService] Rejected Google token from "
                "non-allowlisted service account: sub=%s email=%s",
                sub,
                payload.get("email"),
            )
            raise ValueError("Google Token Invalid: caller not allowed")

        return self._build_context(payload, source="google")

    def _get_cf_signing_key(self, token: str):
        """
        Retrieve the Cloudflare JWT signing key from the token header.

        Uses local cache to reduce JWKS fetch requests.

        Args:
            token (str): Cloudflare JWT token.

        Returns:
            RSAAlgorithm: Public key for verifying the JWT.
        """
        try:
            header = jwt.get_unverified_header(token)
            kid = header.get("kid")
        except Exception:
            raise ValueError("Invalid JWT Header")

        if not kid:
            raise ValueError("Missing kid")

        if kid not in self._CF_JWKS_CACHE:
            with self._jwks_refresh_lock:
                # Re-check inside the lock: another thread may have
                # already refreshed while we were waiting.
                if kid not in self._CF_JWKS_CACHE:
                    self._refresh_cf_keys()
            if kid not in self._CF_JWKS_CACHE:
                raise ValueError("Key not found")

        return self._CF_JWKS_CACHE[kid]

    def _refresh_cf_keys(self):
        """
        Fetch Cloudflare JWKS keys and update the local cache.
        """
        try:
            r = requests.get(self.cf_jwks_url, timeout=5)
            r.raise_for_status()
            for key_dict in r.json().get("keys", []):
                kid = key_dict["kid"]
                self._CF_JWKS_CACHE[kid] = RSAAlgorithm.from_jwk(json.dumps(key_dict))
        except Exception as e:
            self.logger.error(f"JWKS Fetch Failed: {e}")

    def _build_context(self, payload: dict[str, Any], source: str) -> UserContextDto:
        """
        Build the UserContextDto from a token payload.

        Sets only the identity-layer fields the auth layer can know from the
        token: sub, email, identity_type, and is_service_account. Permissions
        and is_super_admin are resolved later (DB-backed) by the middleware's
        resolve_permissions step.

        Args:
            payload (dict): Decoded JWT payload.
            source (str): Source of the token, either "google" or "cloudflare".
        """
        email = ""
        sub = ""
        last_login_at = None
        first_name = ""
        last_name = ""
        identity_type = IdentityType.EXTERNAL
        is_service_account = False
        email_verified = False

        if "google" == source:
            # Google CronJob / service account.
            is_service_account = True
            identity_type = IdentityType.CRONJOB
            email = payload.get("email")
            sub = payload.get("sub")
            last_login_at = payload.get("iat")

        elif "cloudflare" == source:
            custom_claims = payload.get("custom", {})
            email = custom_claims.get("email", "")
            sub = custom_claims.get("sub", "")
            last_login_at = custom_claims.get("iat")
            first_name = custom_claims.get("given_name", "")
            last_name = custom_claims.get("family_name", "")
            email_verified = custom_claims.get("email_verified", False)
            # Internal is keyed off the company email domain, not the login
            # connection, Require email_verified so a connection that lets
            # a user self-assert an unverified address cannot claim a company domain.
            if email_verified and is_company_email(email):
                identity_type = IdentityType.INTERNAL

        return UserContextDto(
            sub=sub,
            primary_email=email,
            identity_type=identity_type,
            is_service_account=is_service_account,
            last_login_at=last_login_at,
            first_name=first_name,
            last_name=last_name,
            email_verified=email_verified,
        )
