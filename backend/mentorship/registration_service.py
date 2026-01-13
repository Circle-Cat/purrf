from sqlalchemy.ext.asyncio import AsyncSession
from backend.dto.registration_create_dto import RegistrationCreateDto
from backend.entity.preference_entity import PreferenceEntity


class RegistrationService:
    """
    Service to handle user preferences related to skills and industry.

    This service is responsible for fetching, updating, and creating user preferences
    for skills, specific industries, and related information.

    Attributes:
        preferences_repo: The repository responsible for handling preference data.
        logger: The logger for logging events during the process.
    """

    def __init__(self, logger, preferences_repository):
        self.preferences_repo = preferences_repository
        self.logger = logger

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
