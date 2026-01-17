from sqlalchemy.ext.asyncio import AsyncSession
from backend.dto.user_context_dto import UserContextDto
from backend.dto.registration_create_dto import RegistrationCreateDto
from backend.dto.preference_dto import SpecificIndustryDto, SkillsetsDto
from backend.dto.registration_dto import GlobalPreferencesDto, RegistrationDto
from backend.entity.preference_entity import PreferenceEntity


class RegistrationService:
    """
    Service to handle user preferences related to skills and industry.

    This service is responsible for fetching, updating, and creating user preferences
    for skills, specific industries, and related information.
    """

    def __init__(
        self,
        logger,
        preferences_repository,
        participation_service,
        user_identity_service,
        mentorship_mapper,
    ):
        """
        Initialize the RegistrationService with its dependencies.

        Args:
            logger: The logger for logging events during the process.
            preferences_repo: The repository responsible for handling preference data.
            participation_service: Service responsible for retrieving participation data.
            user_identity_service: Service responsible for retrieving user identity information.
            mentorship_mapper (MentorshipMapper):
                The mapper for converting mentorship rounds and entities to DTOs.
        """
        self.logger = logger
        self.preferences_repo = preferences_repository
        self.participation_service = participation_service
        self.user_identity_service = user_identity_service
        self.mentorship_mapper = mentorship_mapper

    async def update_skill_and_industry_preferences(
        self, session: AsyncSession, user_id: int, data: RegistrationCreateDto
    ) -> PreferenceEntity:
        """
        Updates or creates a new user preference record based on the provided data.

        This method will either update the existing user preference record or create a new one
        if none is found. It will map the skillset and industry preferences from the provided
        data, and upsert them into the preferences repository.

        Args:
            session (AsyncSession): The SQLAlchemy session for handling database operations.
            user_id (int): The ID of the user whose preferences are being updated.
            data (RegistrationCreateDto): The DTO containing the user's new preferences data.

        Returns:
            PreferenceEntity: The result of the upsert operation.
        """

        preferences_entity = await self.preferences_repo.get_preferences_by_user_id(
            session=session, user_id=user_id
        )

        if not preferences_entity:
            self.logger.info(
                "[RegistrationService] no existing preferences found for user_id: %s. Initializing new record.",
                user_id,
            )
            preferences_entity = PreferenceEntity(user_id=user_id)
        else:
            self.logger.debug(
                "[RegistrationService] existing preferences found for user_id: %s. Updating existing record.",
                user_id,
            )

        global_pref = data.global_preferences

        self.logger.debug(
            "[RegistrationService] mapping skillsets for user_id: %s", user_id
        )
        skill_data = global_pref.skillsets.model_dump()
        for field_name, value in skill_data.items():
            if hasattr(preferences_entity, field_name):
                setattr(preferences_entity, field_name, value)

        if global_pref.specific_industry:
            self.logger.debug(
                "[RegistrationService] updating specific industry JSONB for user_id: %s",
                user_id,
            )
            preferences_entity.specific_industry = (
                global_pref.specific_industry.model_dump()
            )
        else:
            self.logger.debug(
                "[RegistrationService] no specific industry provided; clearing field for user_id: %s",
                user_id,
            )
            preferences_entity.specific_industry = None

        result = await self.preferences_repo.upsert_preference(
            session=session, entity=preferences_entity
        )

        self.logger.info(
            "[RegistrationService] successfully upserted preferences for user_id: %s",
            user_id,
        )
        return result

    async def get_registration_info(
        self, session: AsyncSession, user_context: UserContextDto, round_id: int
    ) -> RegistrationDto:
        """
        Consolidates global and round preferences into a comprehensive registration DTO.

        This method:
        1. Resolves the user ID and handles necessary database commits.
        2. Retrieves both global and round-specific preferences.
        3. Combines both preference DTOs into a unified RegistrationDto.

        Args:
            session (AsyncSession): Active SQLAlchemy async session.
            user_context (UserContextDto): Authenticated user context.
            round_id (int): The ID of the mentorship round.

        Returns:
            RegistrationDto: A DTO combining GlobalPreferenceDTO and RoundPreferenceDto.
        """
        (current_user, should_commit) = await self.user_identity_service.get_user(
            session=session, user_info=user_context
        )

        if should_commit:
            await session.commit()

        current_user_id = current_user.user_id

        global_preferences = await self._get_skill_and_industry_preferences(
            session=session, user_id=current_user_id
        )
        round_preferences = await self.participation_service.get_user_round_preferences(
            session=session,
            user_context=user_context,
            user_id=current_user_id,
            round_id=round_id,
        )

        return RegistrationDto(
            global_preferences=global_preferences, round_preferences=round_preferences
        )

    async def _get_skill_and_industry_preferences(
        self, session: AsyncSession, user_id: int
    ) -> GlobalPreferencesDto:
        """
        Retrieves the user's global skill and industry preferences.

        Args:
            session (AsyncSession): Active SQLAlchemy async session.
            user_id (int): The ID of the current user.

        Returns:
            GlobalPreferencesDto: The user's global preferences, or a default DTO if no record is found.
        """
        preference = await self.preferences_repo.get_preferences_by_user_id(
            session=session, user_id=user_id
        )
        if not preference:
            return GlobalPreferencesDto(
                specific_industry=SpecificIndustryDto(), skillsets=SkillsetsDto()
            )
        return self.mentorship_mapper.map_to_global_preferences_dto(
            preference_entity=preference
        )
