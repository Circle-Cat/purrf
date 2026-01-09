from fastapi import APIRouter, Query

from backend.dto.profile_dto import ProfileDto
from backend.dto.user_context_dto import UserContextDto
from backend.common.fast_api_response_wrapper import api_response
from backend.common.api_endpoints import MY_PROFILE_ENDPOINT
from backend.common.constants import ProfileField
from backend.utils.permission_decorators import authenticate
from backend.dto.profile_create_dto import ProfileCreateDto


class ProfileController:
    """
    FastAPI controller exposing profile-related endpoints.

    Handles authentication, request parsing, and transaction boundaries,
    delegating all business logic to ProfileService.
    """

    def __init__(self, profile_service, database):
        """
        Initialize the ProfileController with its dependencies and register routes.

        Args:
            profile_service (ProfileService): Service handling profile business logic.
            database (Database): Database access object providing async session management.
        """
        self.router = APIRouter(tags=["profile"])
        self.profile_service = profile_service
        self.database = database

        self.router.add_api_route(
            MY_PROFILE_ENDPOINT,
            endpoint=authenticate()(self.get_my_profile),
            methods=["GET"],
            response_model=None,
        )
        self.router.add_api_route(
            MY_PROFILE_ENDPOINT,
            endpoint=authenticate()(self.update_my_profile),
            methods=["PATCH"],
            response_model=None,
        )

    async def get_my_profile(
        self,
        current_user: UserContextDto,
        fields: str | None = Query(None),
    ):
        """
        Retrieve the profile of the currently authenticated user.

        This endpoint returns the authenticated user's profile data. The response
        always includes the user's basic information, while additional profile
        sections can be selectively included using the `fields` query parameter.

        Query Parameters:
            fields (str | None):
                Optional comma-separated list of profile sections to include
                in the response.

        Returns:
            A standardized API response containing the user's profile data.
            The `profile` object will include only the requested sections
            in addition to the basic user information.

        Raises:
            HTTPException:
                - 401 if the user is not authenticated
                - 400 if an invalid field value is provided
        """
        fields_set = (
            {ProfileField(f.strip()) for f in fields.split(",")} if fields else None
        )

        async with self.database.session() as session:
            profile: ProfileDto = await self.profile_service.get_profile(
                session, current_user, fields_set
            )

        return api_response(
            message="Profile retrieved successfully",
            data={"profile": profile},
        )

    async def update_my_profile(
        self,
        current_user: UserContextDto,
        body: ProfileCreateDto,
    ):
        """
        Update the profile of the currently authenticated user.

        This endpoint updates one or more sections of a user's profile based on
        the provided request body. Supported sections include:

        - User basic information (e.g. name, timezone, communication method)
        - Work history
        - Education history

        Only the sections present in the request body will be updated.
        Omitted sections are left unchanged.

        All updates are executed within a single database transaction.

        Args:
            current_user (UserContextDto): Authenticated user context.
            body (ProfileCreateDto): Profile payload containing fields to update.

        Returns:
            A standardized API response containing the updated profile.
        """
        async with self.database.session() as session:
            profile: ProfileDto = await self.profile_service.update_profile(
                session=session, user_context=current_user, profile=body
            )

        return api_response(
            message="Profile updated successfully",
            data={"profile": profile},
        )
