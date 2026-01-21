from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from backend.dto.user_context_dto import UserContextDto
from backend.dto.registration_create_dto import RegistrationCreateDto
from backend.dto.preference_dto import SpecificIndustryDto, SkillsetsDto
from backend.dto.registration_dto import GlobalPreferencesDto, RegistrationDto
from backend.entity.preference_entity import PreferenceEntity
from backend.entity.mentorship_round_participants_entity import (
    MentorshipRoundParticipantsEntity,
)


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
        mentorship_round_repository,
        mentorship_round_participants_repository,
        participation_service,
        user_identity_service,
        mentorship_mapper,
    ):
        """
        Initialize the RegistrationService with its dependencies.

        Args:
            logger: The logger for logging events during the process.
            preferences_repository: The repository responsible for handling preference data.
            mentorship_round_repository: The repository responsible for handling mentorship round data.
            mentorship_round_participants_repository: The repository responsible for handling mentorship
                                                    round participants data.
            participation_service: Service responsible for retrieving participation data.
            user_identity_service: Service responsible for retrieving user identity information.
            mentorship_mapper (MentorshipMapper):
                The mapper for converting mentorship rounds and entities to DTOs.
        """
        self.logger = logger
        self.preferences_repo = preferences_repository
        self.mentorship_round_repo = mentorship_round_repository
        self.participants_repo = mentorship_round_participants_repository
        self.participation_service = participation_service
        self.user_identity_service = user_identity_service
        self.mentorship_mapper = mentorship_mapper

    async def update_registration_info(
        self,
        session: AsyncSession,
        user_context: UserContextDto,
        round_id: int,
        preferences_data: RegistrationCreateDto,
    ) -> RegistrationDto:
        """
        Updates or create a new registration information for current user.

        This method:
        1. Validates the existence of the mentorship round.
        2. Checks if the application deadline has passed. If the round is still open, updates both
            global and round-specific preferences for user.
        3. Commits the changes to the database.

        Args:
            session (AsyncSession): Active SQLAlchemy async session.
            user_context (UserContextDto): Authenticated user context.
            round_id (int): The ID of the mentorship round.
            preferences_data (RegistrationCreateDto): The DTO containing the user's new preferences data.

        Returns:
            RegistrationDto: The DTO containing updated registration information.
        """
        round_entity = await self.mentorship_round_repo.get_by_round_id(
            session=session, round_id=round_id
        )
        if not round_entity:
            self.logger.error(
                "[RegistrationService] user tried to register a non-existent mentorship round %s.",
                round_id,
            )
            raise ValueError(f"Mentorship round {round_id} not found.")

        raw_deadline = (round_entity.description or {}).get("application_deadline_at")
        if not raw_deadline:
            self.logger.error(
                "[RegistrationService] round %s missing application deadline.", round_id
            )
            raise ValueError(f"Round {round_id} missing application deadline.")

        application_deadline = datetime.fromisoformat(raw_deadline).date()
        register_time = datetime.now(timezone.utc).date()

        if register_time > application_deadline:
            self.logger.error(
                "[RegistrationService] registration failed for round %s. Current time %s is past deadline %s.",
                round_id,
                register_time,
                application_deadline,
            )
            raise ValueError(
                f"Registration period has ended at {application_deadline}."
            )

        current_user, _ = await self.user_identity_service.get_user(
            session=session, user_info=user_context
        )

        participant_role = (
            await self.participation_service.resolve_participant_role_with_fallback(
                session=session, user_context=user_context, user_id=current_user.user_id
            )
        )
        preferences_data.round_preferences.participant_role = participant_role

        global_pref = await self._update_skill_and_industry_preferences(
            session=session, user_id=current_user.user_id, data=preferences_data
        )
        round_pref = await self._update_user_round_preferences(
            session=session,
            user_id=current_user.user_id,
            round_id=round_id,
            data=preferences_data,
        )

        await session.commit()

        return RegistrationDto(
            global_preferences=self.mentorship_mapper.map_to_global_preferences_dto(
                global_pref
            ),
            round_preferences=self.mentorship_mapper.map_to_round_preference_dto(
                round_pref
            ),
        )

    async def _update_skill_and_industry_preferences(
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

    async def _update_user_round_preferences(
        self,
        session: AsyncSession,
        user_id: int,
        round_id: int,
        data: RegistrationCreateDto,
    ) -> MentorshipRoundParticipantsEntity:
        """
        Updates or creates a new user round preference record based on the provided data.

        This method will either update the existing user round preference record or create a new one
        if none is found. It will map round preferences from the provided data,
        and upsert them into the participants repository.

        Args:
            session (AsyncSession): The SQLAlchemy session for handling database operations.
            user_id (int): The ID of the user whose round preferences are being updated.
            round_id (int): The ID of the mentorship round.
            data (RegistrationCreateDto): The DTO containing the user's new round preferences data.

        Returns:
            MentorshipRoundParticipantsEntity: The result of the upsert operation.
        """
        entity = await self.participants_repo.get_by_user_id_and_round_id(
            session=session, user_id=user_id, round_id=round_id
        )

        if not entity:
            entity = MentorshipRoundParticipantsEntity(
                user_id=user_id, round_id=round_id
            )

        round_pref = data.round_preferences
        entity.participant_role = round_pref.participant_role
        entity.max_partners = round_pref.max_partners
        entity.expected_partner_user_id = round_pref.expected_partner_ids or []
        entity.unexpected_partner_user_id = round_pref.unexpected_partner_ids or []
        entity.goal = round_pref.goal or ""

        result = await self.participants_repo.upsert_participant(
            session=session, entity=entity
        )

        self.logger.info(
            "[RegistrationService] successfully saved round preferences for user_id: %s, round_id: %s",
            user_id,
            round_id,
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
