from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from backend.common.fast_api_response_wrapper import api_response
from http import HTTPStatus


class AuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware for authenticating incoming HTTP requests.

    This middleware automatically detects and verifies authentication tokens from
    multiple sources, including Cloudflare Access JWTs and Google identity tokens.
    It injects the authenticated user's context into the request state, allowing
    downstream route handlers to access user information and roles.

    Features:
        1. Delegates token verification to `AuthenticationService`.
        2. Adds `request.state.user` containing:
            - sub: Unique identifier
            - primary_email: User's primary email
            - roles: List of user roles (UserRole Enum)
        3. Returns a standardized API response on authentication failure using `api_response`.

    Attributes:
        auth_service: An instance of `AuthenticationService` responsible for token validation.

    Usage:
        app.add_middleware(AuthMiddleware, auth_service=auth_service)

    Exception Handling:
        - ValueError: Returns HTTP 400 BAD REQUEST with the error message.
        - Other exceptions: Returns HTTP 403 FORBIDDEN with "Authentication failed".

    Example:
        @app.get("/dashboard")
        async def dashboard(request: Request):
            user = request.state.user
            if "cc_internal" not in user.roles and "admin" not in user.roles:
                return api_response(
                    message="Forbidden",
                    status_code=HTTPStatus.FORBIDDEN
                )
            return api_response(
                message="Dashboard data",
                data={"user": user.primary_email}
            )
    """

    def __init__(self, app, auth_service):
        super().__init__(app)
        self.auth_service = auth_service

    async def dispatch(self, request: Request, call_next):
        """
        Middleware method to handle authentication for incoming requests.

        This method attempts to validate the request's authentication token using
        `self.auth_service.authenticate_request`. If successful, it attaches the
        user context to `request.state.user` so that downstream handlers can access it.

        If token validation fails with a `ValueError`, a 400 Bad Request response is
        returned with the error message. For other exceptions, a 403 Forbidden response
        is returned with a generic "Authentication failed" message.

        Args:
            request (Request): The incoming FastAPI request object.
            call_next (Callable): The next middleware or route handler to call.

        Returns:
            Response: The response returned by the next handler, or an error response
                    if authentication fails.
        """
        try:
            # Validate token and get user context
            user_context = self.auth_service.authenticate_request(request.headers)
            request.state.user = user_context

        except ValueError as e:
            return api_response(
                message=str(e), status_code=HTTPStatus.BAD_REQUEST, data=None
            )
        except Exception:
            return api_response(
                message="Authentication failed",
                status_code=HTTPStatus.FORBIDDEN,
                data=None,
            )

        return await call_next(request)
