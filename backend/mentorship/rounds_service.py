from backend.mentorship.mentorship_mapper import MentorshipMapper
from backend.repository.mentorship_round_repository import MentorshipRoundRepository
from backend.repository.mentorship_round_participants_repository import (
    MentorshipRoundParticipantsRepository,
)
from backend.repository.mentorship_pairs_repository import MentorshipPairsRepository
from backend.entity.mentorship_round_entity import MentorshipRoundEntity
from backend.dto.rounds_dto import RoundsDto
from backend.dto.rounds_create_dto import RoundsCreateDto

from sqlalchemy.ext.asyncio import AsyncSession


class RoundsService:
    """Service for managing mentorship rounds."""

    def __init__(
        self,
        mentorship_round_repository: MentorshipRoundRepository,
        mentorship_mapper: MentorshipMapper,
        mentorship_round_participants_repository: MentorshipRoundParticipantsRepository,
        mentorship_pairs_repository: MentorshipPairsRepository,
    ):
        """
        Initializes the RoundsService with required dependencies.

        Args:
            mentorship_round_repository (MentorshipRoundRepository):
                The repository for accessing mentorship round data.
            mentorship_mapper (MentorshipMapper):
                The mapper for converting database entities to DTOs.
            mentorship_round_participants_repository (MentorshipRoundParticipantsRepository):
                The repository for participant count queries.
            mentorship_pairs_repository (MentorshipPairsRepository):
                The repository for completed meeting count queries.
        """
        self.mentorship_round_repository = mentorship_round_repository
        self.mentorship_mapper = mentorship_mapper
        self.mentorship_round_participants_repository = (
            mentorship_round_participants_repository
        )
        self.mentorship_pairs_repository = mentorship_pairs_repository

    async def get_all_rounds(
        self, session: AsyncSession, include_details: bool = False
    ) -> list[RoundsDto]:
        """
        Retrieve all mentorship rounds and map them to DTOs.

        Args:
            session (AsyncSession): Active database async session.
            include_details (bool): If True, fetches participant and completed
                meeting counts per round.

        Returns:
            list[RoundsDto]: A list of RoundsDto objects representing the mentorship rounds.
        """
        all_round_entities = await self.mentorship_round_repository.get_all_rounds(
            session
        )

        if not include_details:
            return self.mentorship_mapper.map_to_rounds_dto(all_round_entities)

        participants_counts = await self.mentorship_round_participants_repository.get_participants_count_per_round(
            session
        )
        completed_meetings_per_round = (
            await self.mentorship_pairs_repository.get_completed_meetings_per_round(
                session
            )
        )

        return self.mentorship_mapper.map_to_rounds_dto(
            all_round_entities, participants_counts, completed_meetings_per_round
        )

    async def upsert_rounds(
        self, session: AsyncSession, data: RoundsCreateDto
    ) -> RoundsDto:
        """
        Inserts a new MentorshipRoundEntity object or updates an existing one in the database.

        Args:
            session (AsyncSession): Active database async session.
            data(RoundsCreateDto):The data transfer object containing information about the round.

        Returns:
            RoundsDto: The DTO synchronized with the database, reflecting the latest state,
            generated keys, and default values.
        """

        if data.id is None:
            round = MentorshipRoundEntity()
        else:
            round = await self.mentorship_round_repository.get_by_round_id(
                session, data.id
            )

            if round is None:
                raise ValueError("Round with given ID does not exist.")

        round.name = data.name
        round.mentee_average_score = data.mentee_average_score
        round.mentor_average_score = data.mentor_average_score
        round.expectations = data.expectations
        round.description = data.timeline.model_dump(mode="json", exclude_none=True)
        round.required_meetings = data.required_meetings

        round = await self.mentorship_round_repository.upsert_round(session, round)
        await session.commit()

        return RoundsDto(
            id=round.round_id,
            name=round.name,
            mentee_average_score=round.mentee_average_score,
            mentor_average_score=round.mentor_average_score,
            expectations=round.expectations,
            required_meetings=round.required_meetings,
            timeline=data.timeline,
        )
