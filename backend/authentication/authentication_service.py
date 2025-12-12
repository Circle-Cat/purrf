import jwt
import requests
import json
from typing import Any
from starlette.datastructures import Headers
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from jwt.algorithms import RSAAlgorithm
from backend.common.environment_constants import (
    CF_TEAM_DOMAIN,
    CF_AUD_TAG,
    GOOGLE_AUDIENCE,
)
from backend.dto.user_context_dto import UserContextDto
from backend.common.user_role import UserRole


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

    def _verify_google(self, token: str) -> UserContextDto:
        """
        Verify a Google identity token and construct the user context.

        Args:
            token (str): Google Identity token.

        Returns:
            UserContextDto: User information including roles.
        """
        try:
            payload = id_token.verify_token(
                token, self.google_request, audience=GOOGLE_AUDIENCE
            )
        except ValueError as e:
            raise ValueError(f"Google Token Invalid: {str(e)}")

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
        Build the UserContextDto from token payload based on the source.

        Args:
            payload (dict): Decoded JWT payload.
            source (str): Source of the token, either "google" or "cloudflare".

        Returns:
            UserContextDto: Contains sub, primary_email, and roles.
        """
        roles = []
        email = ""
        sub = ""

        if "google" == source:
            # Google CronJob / Service Account
            roles.append(UserRole.CRON_RUNNER)
            email = payload.get("email")
            sub = payload.get("sub")

        elif "cloudflare" == source:
            # Cloudflare User
            custom_claims = payload.get("custom", {})
            email = custom_claims.get("email", "")
            raw_sub = custom_claims.get("sub", "")
            upn = custom_claims.get("upn", "")
            role_claim = custom_claims.get("extn.purrf_role", [])

            if "admin" in role_claim:
                roles.append(UserRole.ADMIN)

            if upn.endswith("@u.circlecat.org"):
                roles.append(UserRole.CC_INTERNAL)
                sub = f"azure|{raw_sub}"
                email = upn
            elif raw_sub.startswith("google-oauth2|") and email.endswith("@google.com"):
                roles.append(UserRole.CONTACT_GOOGLE_CHAT)
                sub = f"auth0|{raw_sub}"
            else:
                sub = f"auth0|{raw_sub}"

            roles.append(UserRole.MENTORSHIP)

        return UserContextDto(sub=sub, primary_email=email, roles=roles)
