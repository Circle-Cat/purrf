import asyncio
from http import HTTPStatus

from sqlalchemy.exc import IntegrityError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from backend.common.fast_api_response_wrapper import api_response
from backend.common.user_role import IdentityType


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
        database: Database used to open the short bootstrap transaction.
        user_identity_service: Resolves / first-login creates the internal user.

    Usage:
        app.add_middleware(
            AuthMiddleware,
            auth_service=auth_service,
            database=database,
            user_identity_service=user_identity_service,
            logger=logger,
        )

    Exception Handling:
        - ValueError: Returns HTTP 400 BAD REQUEST with the error message.
        - Other exceptions: Returns HTTP 403 FORBIDDEN with "Authentication failed".

    Example:
        @app.get("/dashboard")
        async def dashboard(request: Request):
            user = request.state.user
            if "ccInternal" not in user.roles and "manager" not in user.roles:
                return api_response(
                    message="Forbidden",
                    status_code=HTTPStatus.FORBIDDEN
                )
            return api_response(
                message="Dashboard data",
                data={"user": user.primary_email}
            )
    """

    def __init__(self, app, auth_service, database, user_identity_service, logger):
        super().__init__(app)
        self.auth_service = auth_service
        self.database = database
        self.user_identity_service = user_identity_service
        self.logger = logger

    async def dispatch(self, request: Request, call_next):
        """
        Middleware method to handle authentication for incoming requests.

        This method attempts to validate the request's authentication token using
        `self.auth_service.authenticate_request`. If successful, it attaches the
        user context to `request.state.user` so that downstream handlers can access it.

        If token validation fails with a `ValueError`, a 400 Bad Request response is
        returned with the error message. A `PermissionError` (e.g. a deactivated
        account that authenticates but is barred from acting) returns a 403 with its
        reason. For other exceptions, a 403 Forbidden response is returned with a
        generic "Authentication failed" message.

        Args:
            request (Request): The incoming FastAPI request object.
            call_next (Callable): The next middleware or route handler to call.

        Returns:
            Response: The response returned by the next handler, or an error response
                    if authentication fails.
        """
        try:
            # authenticate_request is synchronous and may issue a blocking
            # JWKS HTTP fetch on cache miss. Offload to a worker thread so
            # the event loop stays free for other requests.
            user_context = await asyncio.to_thread(
                self.auth_service.authenticate_request, request.headers
            )

            # Cron / service-account tokens (identity_type "cronjob") have no
            # user_identities row; skip first-login bootstrap and leave user_id
            # unset. Gating on identity_type keeps this off the permission path.
            if user_context.identity_type != IdentityType.CRONJOB:
                await self._bootstrap_user(user_context)

            request.state.user = user_context

        except ValueError as e:
            return api_response(
                message=str(e), status_code=HTTPStatus.BAD_REQUEST, data=None
            )
        except PermissionError as e:
            self.logger.warning(
                "[AuthMiddleware] %s %s denied: %s",
                request.method,
                request.url.path,
                e,
            )
            return api_response(
                message=(
                    "Your account has been deactivated. "
                    "Contact an administrator to restore access."
                ),
                status_code=HTTPStatus.FORBIDDEN,
                data=None,
            )
        except Exception:
            self.logger.exception(
                "[AuthMiddleware] Auth middleware failed for %s %s",
                request.method,
                request.url.path,
            )
            return api_response(
                message="Authentication failed",
                status_code=HTTPStatus.FORBIDDEN,
                data=None,
            )

        return await call_next(request)

    async def _bootstrap_user(self, user_context):
        """
        Resolve (and on first login create) the internal user for an
        authenticated request, writing user_context.user_id.

        Runs in a short transaction that commits before the request handler
        opens its own session: one SELECT per authenticated request, plus an
        INSERT only on first login.

        Two concurrent first logins for the same sub both miss find_by_sub and
        enter create_or_swap_user; the second collides on the
        subject_identifier UNIQUE constraint, rolls back, and re-finds the row
        the winner committed.
        """
        async with self.database.session() as session:
            async with session.begin():
                user = await self.user_identity_service.find_user_by_sub(
                    session, user_context.sub, user_context.last_login_at
                )
                if user is None:
                    try:
                        # SAVEPOINT around the insert: on a concurrent first
                        # login the unique-violation rolls back only to here,
                        # leaving the outer transaction usable.
                        async with session.begin_nested():
                            user = await self.user_identity_service.create_or_swap_user(
                                session, user_context
                            )
                    except IntegrityError:
                        # A concurrent first login may have won and committed;
                        # re-find its row in the still-open outer transaction.
                        # If nothing is there, this was not the race but a real
                        # constraint violation (e.g. a primary_email already
                        # owned by another user), so surface the original error
                        # instead of masking it as a bogus retry failure.
                        user = await self.user_identity_service.find_user_by_sub(
                            session, user_context.sub, user_context.last_login_at
                        )
                        if user is None:
                            raise

                # A deactivated account still authenticates (valid token, real
                # user) but must not be allowed to act.
                if not user.is_active:
                    raise PermissionError("User account is deactivated")
        user_context.user_id = user.user_id
        self.logger.info(
            "[AuthMiddleware] user login: user_id=%s", user_context.user_id
        )
