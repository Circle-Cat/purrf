from backend.dto.partner_dto import PartnerDto
from backend.dto.user_context_dto import UserContextDto
from sqlalchemy.ext.asyncio import AsyncSession


class ParticipationService:
    """Service to retrieve mentorship participants information."""

    def __init__(
        self,
        logger,
        users_repository,
        mentorship_pairs_repository,
        mentorship_mapper,
        user_identity_service,
    ):
        """
        Initializes the participationService with required dependencies.

        Args:
            logger: The logger instance for logging messages.
            users_repository (UsersRepository):
                The repository for accessing users entity data.
            mentorship_pairs_repository (MentorshipPairsRepository):
                The repository for accessing pairs entity data.
            mentorship_mapper (MentorshipMapper):
                The mapper for converting mentorship rounds and entities to DTOs.
            user_identity_service (UserIdentityService):
                The service for resolving the user ID from the subject identifier.
        """
        self.logger = logger
        self.users_repository = users_repository
        self.mentorship_pairs_repository = mentorship_pairs_repository
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
