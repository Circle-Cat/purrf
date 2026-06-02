from fastapi import APIRouter
from backend.common.fast_api_response_wrapper import api_response
from backend.common.api_endpoints import MY_PERMISSIONS
from backend.utils.permission_decorators import authenticate
from backend.dto.user_context_dto import UserContextDto


class AuthenticationController:
    """
    Controller for user authentication-related endpoints.

    Provides a route to fetch the current user's resolved permissions and basic
    identity. Uses the `@authenticate` decorator to inject the user context into
    `current_user`.

    Endpoints:
        GET /permissions/me: Returns the current user's permissions.
    """

    def __init__(self, user_emails_repository, database):
        self._user_emails_repository = user_emails_repository
        self._database = database
        self.router = APIRouter(tags=["Authentication"])

        # Register route
        self.router.add_api_route(
            MY_PERMISSIONS,
            authenticate()(self.get_my_permissions),
            methods=["GET"],
            response_model=dict,
        )

    async def get_my_permissions(self, current_user: UserContextDto):
        """
        Retrieve the current user's resolved permissions, the super-admin flag,
        and whether they have a confirmed email — the frontend reads
        ``has_verified_email`` to decide whether to hold the user at the
        ``/verify-required`` hard wall.

        Args:
            current_user (UserContextDto): The authenticated user context.

        Returns:
            dict: Standard API response, e.g.:
                {
                    "success": True,
                    "message": "Successfully retrieved user permissions",
                    "data": {
                        "sub": "user-id",
                        "email": "user@example.com",
                        "permissions": ["internal_activity.read"],
                        "is_super_admin": false,
                        "has_verified_email": true
                    }
                }
        """
        has_verified_email = False
        if current_user.user_id is not None:
            async with self._database.session() as session:
                has_verified_email = await self._user_emails_repository.has_confirmed(
                    session, current_user.user_id
                )
        return api_response(
            data={
                "sub": current_user.sub,
                "email": current_user.primary_email,
                "permissions": sorted(str(p) for p in current_user.permissions),
                "is_super_admin": current_user.is_super_admin,
                "has_verified_email": has_verified_email,
            },
            message="Successfully retrieved user permissions",
        )
