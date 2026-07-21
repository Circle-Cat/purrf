import asyncio
from datetime import datetime, timezone
from http import HTTPStatus

from sqlalchemy.exc import IntegrityError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from backend.common.fast_api_response_wrapper import api_response
from backend.common.identity_type import is_rowless_login
from backend.common.permissions import (
    Permission,
    SERVICE_ACCOUNT_PERMISSIONS,
    SUPER_ADMIN_PERMISSIONS,
)

# Maps stored permission_name strings back to Permission members; unknown
# (stale) names are skipped during resolution.
_PERMISSION_BY_VALUE = {p.value: p for p in Permission}


class AuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware for authenticating incoming HTTP requests.

    This middleware automatically detects and verifies authentication tokens from
    multiple sources, including Cloudflare Access JWTs and Google identity tokens.
    It injects the authenticated user's context into the request state, allowing
    downstream route handlers to access user information and permissions.

    Features:
        1. Delegates token verification to `AuthenticationService`.
        2. Adds `request.state.user` containing:
            - sub: Unique identifier
            - primary_email: User's primary email
            - permissions: frozenset[Permission] resolved from the DB
            - is_super_admin / is_service_account: identity-layer flags
        3. Returns a standardized API response on authentication failure using `api_response`.

    Attributes:
        auth_service: An instance of `AuthenticationService` responsible for token validation.
        database: Database used to open the short bootstrap transaction.
        user_identity_service: Resolves / first-login creates the internal user.
        user_permissions_repository: Reads active permission grants during resolve.

    Usage:
        app.add_middleware(
            AuthMiddleware,
            auth_service=auth_service,
            database=database,
            user_identity_service=user_identity_service,
            user_permissions_repository=user_permissions_repository,
            logger=logger,
        )

    Exception Handling:
        - ValueError: Returns HTTP 400 BAD REQUEST with the error message.
        - Other exceptions: Returns HTTP 403 FORBIDDEN with "Authentication failed".

    Example:
        @app.get("/dashboard")
        async def dashboard(current_user: UserContextDto):
            if not current_user.has_permission(Permission.INTERNAL_ACTIVITY_READ):
                return api_response(
                    message="Forbidden",
                    status_code=HTTPStatus.FORBIDDEN
                )
            return api_response(
                message="Dashboard data",
                data={"user": current_user.primary_email}
            )
    """

    def __init__(
        self,
        app,
        auth_service,
        database,
        user_identity_service,
        user_permissions_repository,
        logger,
    ):
        super().__init__(app)
        self.auth_service = auth_service
        self.database = database
        self.user_identity_service = user_identity_service
        self.user_permissions_repository = user_permissions_repository
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

            # Service accounts (Google cron tokens) have no users row, so they
            # skip first-login bootstrap and resolve to a fixed code bundle.
            # Human users are bootstrapped and their permissions resolved from
            # the DB.
            if user_context.is_service_account:
                user_context.permissions = SERVICE_ACCOUNT_PERMISSIONS
            else:
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
        authenticated request, then resolve its permissions onto user_context
        (user_id, is_super_admin, permissions).

        Runs in a short transaction that commits before the request handler
        opens its own session. For users with a matching user_identities row
        (sub-routed), this is one SELECT plus the permission lookup. Passwordless
        users resolved by confirmed-address routing have no identity row and instead
        re-resolve through create_or_swap_user on each request—multiple SELECTs
        to check for email ownership, but no writes in the steady state.

        create_or_swap_user always returns a user (untrusted and stale logins
        are refused upstream, so every login reaching this point is trusted
        and resolves to a row via swap, routing, or first-login).

        Two concurrent first logins for the same sub both miss find_by_sub and
        enter create_or_swap_user; the second collides on the
        subject_identifier UNIQUE constraint, rolls back, and re-finds the row
        the winner committed. If it's still missing, the violation isn't the
        race and must surface.

        Also stamps the account-level users.last_login_at on every successful
        sign-in, so the timestamp stays complete regardless of which identity
        path (sub-routed, swapped, email-routed, or first-login) resolved the user.
        """
        async with self.database.session() as session:
            async with session.begin():
                rowless = is_rowless_login(
                    user_context.sub, user_context.identity_type
                )
                user = None
                if not rowless:
                    # Sub-routed (google / INTERNAL, incl. corp passwordless):
                    # single JOIN resolves the steady state.
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
                        # A concurrent first login committed the winner.
                        if rowless:
                            # Row-less winner wrote no identity row — re-resolve
                            # by confirmed address (routes to the winner).
                            user = await self.user_identity_service.create_or_swap_user(
                                session, user_context
                            )
                        else:
                            # Sub-routed winner recorded its sub — re-find it.
                            user = await self.user_identity_service.find_user_by_sub(
                                session, user_context.sub, user_context.last_login_at
                            )
                        if user is None:
                            # Not the race — a real bug. Must surface.
                            raise

                # A deactivated account still authenticates (valid token, real
                # user) but must not be allowed to act.
                if not user.is_active:
                    raise PermissionError("User account is deactivated")

                # Account-level last-login: every successful human sign-in
                # path (sub-routed, swapped, or email-routed) lands here, so
                # the column stays complete when passwordless logins stop
                # touching user_identities. Written only when the token iat
                # is newer — within a session the iat is constant, so the
                # steady state adds no UPDATE.
                if user_context.last_login_at is not None:
                    login_dt = datetime.fromtimestamp(
                        user_context.last_login_at, tz=timezone.utc
                    )
                    if user.last_login_at is None or user.last_login_at < login_dt:
                        user.last_login_at = login_dt

                await self._resolve_permissions(session, user, user_context)

    async def _resolve_permissions(self, session, user, user_context):
        """
        Resolve a human user's permissions. super_admin short-circuits
        to the full enum; everyone else gets their active user_permissions rows.
        Runs in the bootstrap transaction so the user row is not yet expired.
        """
        user_context.user_id = user.user_id
        self.logger.info(
            "[AuthMiddleware] user login: user_id=%s", user_context.user_id
        )
        # The DB flag is authoritative; the auth layer only sets the DTO flag in
        # local dev (DevAuthenticationService), never in production.
        user_context.is_super_admin = user.is_super_admin or user_context.is_super_admin
        if user_context.is_super_admin:
            user_context.permissions = SUPER_ADMIN_PERMISSIONS
            return
        names = await self.user_permissions_repository.get_active_permission_names(
            session, user.user_id
        )
        unknown = [name for name in names if name not in _PERMISSION_BY_VALUE]
        if unknown:
            self.logger.warning(
                "[AuthMiddleware] user_id=%s has unmapped permission grants %s; skipping",
                user.user_id,
                unknown,
            )
        user_context.permissions = frozenset(
            _PERMISSION_BY_VALUE[name] for name in names if name in _PERMISSION_BY_VALUE
        )
