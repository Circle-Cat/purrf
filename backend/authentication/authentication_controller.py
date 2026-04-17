from fastapi import APIRouter
from backend.common.fast_api_response_wrapper import api_response
from backend.common.api_endpoints import MY_ROLES
from backend.utils.permission_decorators import authenticate
from backend.dto.user_context_dto import UserContextDto


class AuthenticationController:
    """
    Controller for user authentication-related endpoints.

    This controller provides routes to fetch the currently authenticated user's roles
    and basic user information. It uses the `@authenticate` decorator to inject the user context
    into `current_user`.

    Endpoints:
        GET /roles/me: Returns the roles of the current user.
    """

    def __init__(self):
        self.router = APIRouter(tags=["Authentication"])

        # Register route
        self.router.add_api_route(
            MY_ROLES,
            authenticate()(self.get_my_roles),
            methods=["GET"],
            response_model=dict,
        )

    async def get_my_roles(self, current_user: UserContextDto):
        """
        Retrieve the roles of the currently authenticated user.

        Args:
            current_user (UserContextDto): The authenticated user context, including:
                - sub (str): The unique user identifier.
                - primary_email (str): The user's primary email address.
                - roles (List[str]): The list of roles assigned to the user.

        Returns:
            dict: Standard API response containing user identity and roles, e.g.:
                {
                    "success": True,
                    "message": "Successfully retrieved user roles",
                    "data": {
                        "sub": "user-id",
                        "email": "user@example.com",
                        "roles": ["ccInternal", "mentorship"]
                    }
                }
        """
        return api_response(
            data={
                "sub": current_user.sub,
                "email": current_user.primary_email,
                "roles": current_user.roles,
            },
            message="Successfully retrieved user roles",
        )
