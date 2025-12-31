from backend.mentorship.mentorship_mapper import MentorshipMapper
from backend.repository.mentorship_round_repository import MentorshipRoundRepository
from backend.dto.rounds_dto import RoundsDto
from sqlalchemy.ext.asyncio import AsyncSession


class RoundsService:
    """Service for managing mentorship rounds."""

    def __init__(
        self,
        mentorship_round_repository: MentorshipRoundRepository,
        mentorship_mapper: MentorshipMapper,
    ):
        """
        Initializes the RoundsService with required dependencies.

        Args:
            mentorship_round_repository (MentorshipRoundRepository):
                The repository for accessing mentorship round data.
            mentorship_mapper (MentorshipMapper):
                The mapper for converting database entities to DTOs.
        """
        self.mentorship_round_repository = mentorship_round_repository
        self.mentorship_mapper = mentorship_mapper

    async def get_all_rounds(self, session: AsyncSession) -> list[RoundsDto]:
        """
        Retrieve all mentorship rounds and map them to DTOs.

        Args:
            session (AsyncSession): Active database async session.

        Returns:
            list[RoundsDto]: A list of RoundsDto objects representing the mentorship rounds.
        """
        all_round_entities = await self.mentorship_round_repository.get_all_rounds(
            session
        )

        return self.mentorship_mapper.map_to_rounds_dto(all_round_entities)
