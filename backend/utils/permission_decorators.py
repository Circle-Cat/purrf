import functools
import inspect
from http import HTTPStatus
from starlette.requests import Request
from backend.common.fast_api_response_wrapper import api_response


def authenticate(roles: list = None):
    """
    A generic authentication and authorization decorator for FastAPI endpoints.

    This decorator performs the following:
    1. Ensures a user object exists in `request.state.user`.
    2. Optionally checks whether the user has at least one of the required roles.
    3. Injects user-related parameters into the wrapped function if needed.

    Args: roles: A list of roles allowed to access the endpoint.
                  - If None (default), only checks that the user exists.
                  - If provided, the user must have at least one role in this list.
                  - If the wrapped function does not require user-related parameters,
                    this decorator acts as a simple login check.
    Returns: The decorated async function.

    Examples:
        1. Role-based check with user_sub injection:
           @authenticate(roles=["admin", "cc_internal"])
           async def delete_item(item_id: str, user_sub: str):
               # user_sub is automatically injected from request.state.user.sub
               print(f"User {user_sub} is deleting {item_id}")

        2. Manual binding in a Controller constructor (Recommended for Router setup):
           class MyController:
               def __init__(self):
                   self.router = APIRouter()
                   self.router.add_api_route(
                       "/cleanup",
                       endpoint=authenticate(roles=["admin"])(self.cleanup),
                       methods=["POST"]
                   )

               async def cleanup(self, payload: dict, current_user: any):
                   # current_user is injected, and 'request' is filtered out
                   print("Admin %s starting cleanup", current_user.primary_email)
    """

    def decorator(func):
        """
        The actual decorator that wraps the target function.

        Args: func: The endpoint function to be wrapped.
        Returns: The wrapped async function with authentication logic applied.
        """
        sig = inspect.signature(func)
        params = sig.parameters

        @functools.wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            """
            Wrapper function that enforces authentication/authorization
            before calling the original endpoint.

            Args: request: Starlette/FastAPI Request object.
            Args: args: Positional arguments passed to the endpoint.
            Args: kwargs: Keyword arguments passed to the endpoint.
            Returns: API response from either the auth check or the endpoint.
            """
            # Retrieve the user from request state (set by auth middleware)
            user = getattr(request.state, "user", None)
            if not user:
                return api_response(
                    success=False,
                    message="Unauthorized: User context missing",
                    status_code=HTTPStatus.UNAUTHORIZED,
                )

            # Role-based authorization check (if roles are specified)
            if roles is not None:
                user_roles = user.roles
                if not any(role in user_roles for role in roles):
                    return api_response(
                        success=False,
                        message="Forbidden: Insufficient permissions",
                        status_code=HTTPStatus.FORBIDDEN,
                    )

            # Remove framework-specific arguments and keep only business parameters
            business_kwargs = {k: v for k, v in kwargs.items() if k != "request"}

            # Inject the current user if the function expects it
            if "current_user" in params:
                business_kwargs["current_user"] = user

            # Inject user sub if the function expects it
            if "user_sub" in params:
                business_kwargs["user_sub"] = getattr(user, "sub", None)

            return await func(*args, **business_kwargs)

        return wrapper

    return decorator
