from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.constants import ProfileField
from backend.dto.profile_dto import ProfileDto
from backend.dto.user_context_dto import UserContextDto
from backend.profile.profile_query_service import ProfileQueryService
from backend.profile.profile_command_service import ProfileCommandService


class ProfileService:
    """
    Application service responsible for orchestrating profile retrieval.

    This service:
    - Decides which profile fields to load
    - Ensures user existence (create if missing)
    - Delegates all DB access to query/command services
    """

    def __init__(
        self,
        query_service: ProfileQueryService,
        command_service: ProfileCommandService,
    ):
        """
        Initialize the ProfileService with its dependencies.

        Args:
            query_service (ProfileQueryService): Service responsible for reading profile data from the database.
            command_service (ProfileCommandService): Service responsible for writing/updating profile data in the database.
        """
        self.query_service = query_service
        self.command_service = command_service

    async def get_profile(
        self,
        session: AsyncSession,
        user_context: UserContextDto,
        fields: set[ProfileField] | None = None,
    ) -> ProfileDto:
        """
        Retrieve a user profile. If the user does not exist, it will be created.

        Args:
            session (AsyncSession): Active DB session.
            user_context (UserContextDto): Authenticated user context.
            fields (set[ProfileField] | None): Requested profile fields.

        Returns:
            ProfileDto: Profile containing only requested fields.
        """
        if fields is None:
            fields = set(ProfileField)

        includes = {
            "include_training": ProfileField.TRAINING in fields,
            "include_work_history": ProfileField.WORK_HISTORY in fields,
            "include_education": ProfileField.EDUCATION in fields,
        }

        profile = await self.query_service.get_profile(
            session=session,
            user_sub=user_context.sub,
            **includes,
        )

        if profile is None:
            await self.command_service.create_user(session, user_context)
            await session.commit()

            profile = await self.query_service.get_profile(
                session=session,
                user_sub=user_context.sub,
                **includes,
            )

        return profile
