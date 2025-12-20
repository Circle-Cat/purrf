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
from backend.common.user_role import UserRole


class DevAuthenticationService(AuthenticationService):
    """
    Authentication service used exclusively in development mode.

    This service skips real token validation and always returns a
    predefined super-admin user. It should never be used in production
    environments.
    """

    def authenticate_request(self, headers: Headers) -> UserContextDto:
        return UserContextDto(
            sub="dev_superuser",
            primary_email="admin@dev.local",
            roles=[
                UserRole.ADMIN,
                UserRole.CC_INTERNAL,
                UserRole.MENTORSHIP,
                UserRole.CONTACT_GOOGLE_CHAT,
            ],
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
