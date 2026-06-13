"""
Development ASGI entry point for the FastAPI backend application.

This script performs the following steps:
1. Builds application dependencies via AppDependencyBuilder.
2. Creates the FastAPI application instance with all controllers/services injected.
3. Runs the application using Uvicorn ASGI server.
"""

import uvicorn
from backend.utils.app_dependency_builder import AppDependencyBuilder
from starlette.datastructures import Headers
from backend.authentication.authentication_service import AuthenticationService
from backend.dto.user_context_dto import UserContextDto


class DevAuthenticationService(AuthenticationService):
    """
    Authentication service used exclusively in development mode.

    Skips real token validation and returns a fixed, already-verified
    super-admin user. ``is_super_admin=True`` makes resolve_permissions grant
    the full Permission set, so every endpoint is reachable; being "verified"
    (an ``email|`` sub plus ``email_verified=True``) lands a confirmed primary
    email on first login so the hard wall passes — no Auth0 env or OTP needed to
    work on unrelated features.

    To exercise the real email-link flow instead, temporarily set ``sub`` to a
    real Auth0 primary user's sub (e.g. ``google-oauth2|<id>``) and the matching
    ``primary_email``; link_identity needs a real Auth0 user to merge into.
    Never use this service in production.
    """

    def authenticate_request(self, headers: Headers) -> UserContextDto:
        return UserContextDto(
            sub="email|dev-superuser",
            primary_email="admin@dev.local",
            # Verified, so first login lands a confirmed primary email and the
            # hard wall passes without touching Auth0.
            email_verified=True,
            # Full access in dev; resolve_permissions honors this DTO flag
            # (only DevAuthenticationService sets it, never production auth).
            is_super_admin=True,
            # Stand-in for the Auth0 token iat; bump it to see last_login_at
            # advance on the next login.
            last_login_at=1748000000,
        )


# Build application dependencies
builder = AppDependencyBuilder()

# Override the default authentication service with the development version.
# This bypasses real token validation and injects a fixed super-admin user.
# Only use this in local development environments — NEVER in production.
dev_auth_service = DevAuthenticationService(logger=builder.logger)
builder.fast_app_factory.authentication_service = dev_auth_service

# Create FastAPI app with injected dependencies
app = builder.fast_app_factory.create_app()
# Run the ASGI server (development mode)
if __name__ == "__main__":
    uvicorn.run(
        "backend.fast_app_dev_runner:app", host="0.0.0.0", port=5001, reload=True
    )
