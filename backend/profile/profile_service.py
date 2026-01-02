from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.constants import ProfileField
from backend.dto.profile_dto import ProfileDto
from backend.dto.user_context_dto import UserContextDto
from backend.dto.profile_create_dto import ProfileCreateDto


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
        query_service,
        command_service,
        user_identity_service,
    ):
        """
        Initialize the ProfileService with its dependencies.

        Args:
            query_service (ProfileQueryService): Service responsible for reading profile data from the database.
            command_service (ProfileCommandService): Service responsible for writing/updating profile data in the database.
            user_identity_service (UserIdentityService): Service responsible for retrieving user identity information.
        """
        self.query_service = query_service
        self.command_service = command_service
        self.user_identity_service = user_identity_service

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

    async def update_profile(
        self,
        session: AsyncSession,
        user_sub: str,
        profile: ProfileCreateDto,
    ) -> ProfileDto:
        """
        Update the authenticated user's profile.

        This method performs a **partial update** on the user's profile.
        Only the sections present in the incoming `ProfileCreateDto` will be updated;
        omitted sections will remain unchanged.

        Supported update sections:
        - user: Basic user information (name, timezone, communication preferences, etc.)
        - education: Education history (stored as JSONB)
        - work_history: Work experience history (stored as JSONB)

        Return behavior:
        - After the update is committed, the method re-queries the profile and returns
        a fully populated `ProfileDto`.

        Args:
            session (AsyncSession): Active SQLAlchemy async session.
            user_sub (str): Subject identifier of the authenticated user.
            profile (ProfileCreateDto): Incoming profile data containing the fields
                to be updated. Only non-null sections will be applied.

        Returns:
            ProfileDto: The updated user profile after all changes have been persisted.
        """
        users_entity = await self.user_identity_service.get_user_by_subject_identifier(
            session=session, subject=user_sub
        )

        if profile.user:
            await self.command_service.update_users(
                session=session, latest_profile=profile, users=users_entity
            )

        if profile.education:
            await self.command_service.update_education(
                session=session, latest_profile=profile, user_id=users_entity.user_id
            )

        if profile.work_history:
            await self.command_service.update_work_history(
                session=session, latest_profile=profile, user_id=users_entity.user_id
            )

        await session.commit()

        updated_profile = await self.query_service.get_profile(
            session=session,
            user_sub=user_sub,
            include_training=True,
            include_work_history=True,
            include_education=True,
        )

        return updated_profile
