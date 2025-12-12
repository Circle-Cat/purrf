from fastapi import APIRouter, Request
from backend.common.fast_api_response_wrapper import api_response
from backend.common.api_endpoints import MY_ROLES


class AuthenticationController:
    """
    Controller for user authentication-related endpoints.

    This controller provides routes to fetch the currently authenticated user's roles
    and basic user information. It relies on `AuthMiddleware` to inject the user context
    into `request.state.user`.

    Endpoints:
        GET /roles/me: Returns the roles of the current user.
    """

    def __init__(self):
        self.router = APIRouter(tags=["Authentication"])

        # Register route
        self.router.add_api_route(
            MY_ROLES,
            self.get_my_roles,
            methods=["GET"],
            response_model=dict,
        )

    async def get_my_roles(self, request: Request):
        """
        Get the current authenticated user's roles.

        Args:
            request (Request): The FastAPI request object. Assumes that
                               `request.state.user` has been populated by
                               AuthMiddleware.
        Example:
            {
                "success": True,
                "message": "Successfully",
                "data": {
                    "roles": ["cc_internal", "mentorship"]
                }
            }
        """
        user = getattr(request.state, "user")
        return api_response(data={"roles": user.roles}, message="Successfully")
