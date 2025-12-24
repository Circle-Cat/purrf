import functools
import inspect
from http import HTTPStatus
from starlette.requests import Request
from backend.common.fast_api_response_wrapper import api_response
from enum import Enum


class ApiParamName(str, Enum):
    REQUEST = "request"
    CURRENT_USER = "current_user"
    USER_SUB = "user_sub"


def authenticate(roles: list = None):
    """
    A generic authentication and authorization decorator for FastAPI endpoints.

    This decorator works by **rewriting the endpoint function signature**
    to explicitly include a `request: Request` parameter, allowing FastAPI
    to inject the Request object automatically, while keeping business
    parameters clean and explicit.

    This decorator performs the following:
    1. Ensures a user object exists in `request.state.user`.
    2. Optionally checks whether the user has at least one of the required roles.
    3. Injects user-related parameters into the wrapped function if needed.
    4. Filters out framework-only parameters before calling business logic.

    Supported injectable parameters (by name):
    - `request`      → Starlette/FastAPI Request object
    - `current_user` → Full user object from `request.state.user`
    - `user_sub`     → `user.sub` shortcut value

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

               async def cleanup(self, payload: dict, current_user: UserContextDto):
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
        original_params = sig.parameters

        api_params = [
            p
            for name, p in original_params.items()
            if name
            not in {
                ApiParamName.USER_SUB.value,
                ApiParamName.CURRENT_USER.value,
                ApiParamName.REQUEST.value,
            }
        ]

        # Ensure the signature includes `request` so that FastAPI can detect it
        # and inject the Starlette/FastAPI Request object automatically.
        api_params.insert(
            0,
            inspect.Parameter(
                "request", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=Request
            ),
        )

        @functools.wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            """
            Wrapper function that enforces authentication/authorization
            before calling the original endpoint.

            Execution flow:
            1. Reads `request.state.user` populated by auth middleware.
            2. Validates user existence (401 if missing).
            3. Performs optional role check (403 if insufficient).
            4. Constructs business-only kwargs by:
                - Removing framework-injected `request`
                - Injecting `request`, `current_user`, `user_sub`
                only if declared in the original function signature.
            5. Invokes the original endpoint with cleaned arguments.

            Args:
                - request: Starlette/FastAPI Request object.
                - *args: Positional arguments passed to the endpoint.
                - **kwargs: Keyword arguments passed to the endpoint.

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
                user_roles = getattr(user, "roles", None) or []
                if not any(role in user_roles for role in roles):
                    return api_response(
                        success=False,
                        message="Forbidden: Insufficient permissions",
                        status_code=HTTPStatus.FORBIDDEN,
                    )

            # Remove framework-specific arguments and keep only business parameters
            business_kwargs = {
                k: v for k, v in kwargs.items() if k != ApiParamName.REQUEST.value
            }

            if ApiParamName.REQUEST.value in original_params:
                business_kwargs[ApiParamName.REQUEST.value] = request

            if ApiParamName.CURRENT_USER.value in original_params:
                business_kwargs[ApiParamName.CURRENT_USER.value] = user

            if ApiParamName.USER_SUB.value in original_params:
                business_kwargs[ApiParamName.USER_SUB.value] = getattr(
                    user, "sub", None
                )

            return await func(*args, **business_kwargs)

        wrapper.__signature__ = sig.replace(parameters=api_params)
        return wrapper

    return decorator
