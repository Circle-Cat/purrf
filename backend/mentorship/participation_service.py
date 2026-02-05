from backend.dto.partner_dto import PartnerDto
from backend.dto.matches_dto import MatchesDto
from backend.dto.user_context_dto import UserContextDto
from backend.dto.registration_dto import RoundPreferencesDto
from backend.common.mentorship_enums import ParticipantRole
from backend.common.user_role import UserRole
from sqlalchemy.ext.asyncio import AsyncSession
from backend.common.mentorship_enums import (
    ApprovalStatus,
    MatchStatus,
)


class ParticipationService:
    """Service to retrieve mentorship participants information."""

    def __init__(
        self,
        logger,
        users_repository,
        mentorship_pairs_repository,
        mentorship_round_participants_repo,
        mentorship_mapper,
        user_identity_service,
    ):
        """
        Initializes the ParticipationService with required dependencies.

        Args:
            logger: The logger instance for logging messages.
            users_repository (UsersRepository):
                The repository for accessing users entity data.
            mentorship_pairs_repository (MentorshipPairsRepository):
                The repository for accessing pairs entity data.
            mentorship_round_participants_repo (MentorshipRoundParticipantsRepository):
                The repository for accessing participants entity data.
            mentorship_mapper (MentorshipMapper):
                The mapper for converting mentorship rounds and entities to DTOs.
            user_identity_service (UserIdentityService):
                The service for resolving the user ID from the subject identifier.
        """
        self.logger = logger
        self.users_repository = users_repository
        self.mentorship_pairs_repository = mentorship_pairs_repository
        self.mentorship_round_participants_repo = mentorship_round_participants_repo
        self.mentorship_mapper = mentorship_mapper
        self.user_identity_service = user_identity_service

    async def _get_partners_info(
        self, session: AsyncSession, partners_id_list: list[int]
    ) -> list[PartnerDto]:
        """
        Retrieve partial partner information and map it to DTOs.

        Args:
            session (AsyncSession): Active database async session.
            partners_id_list (list): A list of user IDs representing the partners.

        Returns:
            list[PartnerDto]: A list of PartnerDto objects representing the matched users,
                            or an empty list if no users are found.
        """
        partner_user_entities = await self.users_repository.get_all_by_ids(
            session=session, user_ids=partners_id_list
        )

        if not partner_user_entities:
            self.logger.warning(
                "No partner users found for partner_ids=%s", partners_id_list
            )
            return []

        return self.mentorship_mapper.map_to_partner_dto(partner_user_entities)

    async def resolve_participant_role_with_fallback(
        self, session: AsyncSession, user_context: UserContextDto, user_id: int
    ) -> ParticipantRole:
        """
        Resolve the participant role using a temporary fallback strategy.

        This method infers participant role when:
        - the current round participant record does not exist.
        - role auto-assignment and user self-selection are not implemented yet.

        Resolution order:
        1. Use the most recent round participant role.
        2. Infer from user permissions.

        Args:
            session (AsyncSession): Active database async session.
            user_context (UserContextDto): Authenticated user context.
            user_id (int): The ID of the current user.

        Returns:
            ParticipantRole: ParticipantRole: The inferred or resolved role (either 'MENTOR' or 'MENTEE').
        """
        recent_participant = await self.mentorship_round_participants_repo.get_recent_participant_by_user_id(
            session=session, user_id=user_id
        )

        if recent_participant:
            return recent_participant.participant_role

        if user_context.has_role(UserRole.CONTACT_GOOGLE_CHAT):
            return ParticipantRole.MENTOR

        return ParticipantRole.MENTEE

    async def get_partners_for_user(
        self,
        session: AsyncSession,
        user_context: UserContextDto,
        round_id: int | None = None,
    ) -> list[PartnerDto]:
        """
        Retrieve partial partner information for current user and map it to DTOs.

        This method:
        1. Resolves the internal user ID based on the provided UserContextDto.
        2. Determines the applicable mentorship round scope:
            - If round_id is provided, return partners associated with the current user
                in the specified mentorship round.
            - If round_id is not provided, return partners associated with the current user
                across all mentorship rounds.
        3. Returns partners associated with the current user within the resolved round scope.

        Args:
            session (AsyncSession): Active database async session.
            user_context (UserContextDto): Authenticated user context.
            round_id (int | None): The ID of the mentorship round to filter by.

        Returns:
            list[PartnerDto]: A list of PartnerDto objects representing the matched users,
                            or an empty list if no users are found.
        """
        (current_user, should_commit) = await self.user_identity_service.get_user(
            session=session, user_info=user_context
        )

        if should_commit:
            await session.commit()

        current_user_id = current_user.user_id

        if round_id:
            partner_ids = await self.mentorship_pairs_repository.get_partner_ids_by_user_and_round(
                session=session, user_id=current_user_id, round_id=round_id
            )
        else:
            partner_ids = await self.mentorship_pairs_repository.get_all_partner_ids(
                session=session, user_id=current_user_id
            )

        if not partner_ids:
            self.logger.info(
                "No partners found for user_id=%s, round_id=%s",
                current_user_id,
                round_id,
            )
            return []

        return await self._get_partners_info(
            session=session, partners_id_list=partner_ids
        )

    async def get_user_round_preferences(
        self,
        session: AsyncSession,
        user_context: UserContextDto,
        user_id: int,
        round_id: int,
    ) -> tuple[RoundPreferencesDto, bool]:
        """
        Retrieves preferences for a specific mentorship round with historical fallback.

        This method:
        1. Attempts to fetch participation records for the specified round.
        2. If no record is found, it falls back to the most recent historical participation.
        3. For new participants with no history, it provides a default configuration with an inferred role.

        Args:
            session (AsyncSession): Active SQLAlchemy async session.
            user_context (UserContextDto): Authenticated user context.
            user_id (int): The ID of the current user.
            round_id (int): The ID of the mentorship round.

        Returns:
            tuple[RoundPreferencesDto, bool]
                - RoundPreferencesDto: The resolved round-specific preferences.
                - bool: Whether the user has registered for this round.
        """
        is_registered = False
        participant = (
            await self.mentorship_round_participants_repo.get_by_user_id_and_round_id(
                session=session, user_id=user_id, round_id=round_id
            )
        )
        if participant:
            is_registered = True
        else:
            participant = await self.mentorship_round_participants_repo.get_recent_participant_by_user_id(
                session=session, user_id=user_id
            )

        if participant:
            return self.mentorship_mapper.map_to_round_preference_dto(
                participants_entity=participant,
            ), is_registered

        participant_role = await self.resolve_participant_role_with_fallback(
            session=session, user_context=user_context, user_id=user_id
        )

        return RoundPreferencesDto(
            participant_role=participant_role,
            expected_partner_ids=[],
            unexpected_partner_ids=[],
            max_partners=1,
            goal="",
        ), is_registered

    async def get_my_match_result_by_round_id(
        self, session: AsyncSession, user_context: UserContextDto, round_id: int
    ) -> MatchesDto:
        """
        Retrieve the current user's mentorship match result for a specific round.

        This method resolves the current user from the provided user context,
        determines the user's participation and matching status for the given
        mentorship round, and returns the corresponding match result.

        If the user is not in a MATCHED state, an empty partners list is returned
        along with the current match status. If the user is MATCHED, this method
        retrieves all mentorship pairs involving the user and constructs partner
        details for each matched counterpart.

        Args:
            session (AsyncSession): The SQLAlchemy async session used for database operations.
            user_context (UserContextDto): Context information used to identify the current user.
            round_id (int): The mentorship round ID to retrieve match results for.

        Returns:
            MatchesDto:
                An object containing:
                - round_id: The mentorship round ID.
                - current_status: The user's match status for the round.
                - partners: A list of PartnerDto objects representing matched partners.
        """
        current_user, should_commit = await self.user_identity_service.get_user(
            session=session, user_info=user_context
        )
        if should_commit:
            await session.commit()
        uid = current_user.user_id

        participant = (
            await self.mentorship_round_participants_repo.get_by_user_id_and_round_id(
                session=session, user_id=uid, round_id=round_id
            )
        )

        status_map = {
            ApprovalStatus.SIGNED_UP: MatchStatus.PENDING,
            ApprovalStatus.UN_MATCHED: MatchStatus.UNMATCHED,
            ApprovalStatus.REJECTED: MatchStatus.REJECTED,
            ApprovalStatus.MATCHED: MatchStatus.MATCHED,
        }
        current_status = (
            status_map.get(participant.approval_status, MatchStatus.UNKNOWN)
            if participant
            else MatchStatus.UNREGISTERED
        )

        partners: list[PartnerDto] = []

        if current_status != MatchStatus.MATCHED:
            return MatchesDto(
                round_id=round_id, current_status=current_status, partners=partners
            )

        pairs_data = await self.mentorship_pairs_repository.get_pairs_with_partner_info(
            session=session, user_id=uid, round_id=round_id
        )

        for pair, p_user in pairs_data:
            partners.append(
                PartnerDto(
                    id=p_user.user_id,
                    preferred_name=p_user.preferred_name,
                    first_name=p_user.first_name,
                    last_name=p_user.last_name,
                    primary_email=p_user.primary_email,
                    participant_role=ParticipantRole.MENTEE
                    if pair.mentor_id == uid
                    else ParticipantRole.MENTOR,
                    recommendation_reason=pair.recommendation_reason,
                )
            )

        return MatchesDto(
            round_id=round_id, current_status=current_status, partners=partners
        )
