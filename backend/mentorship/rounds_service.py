from datetime import date, datetime, timezone

from backend.mentorship.mentorship_mapper import MentorshipMapper
from backend.repository.mentorship_round_repository import MentorshipRoundRepository
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
        round.description = data.timeline.to_db_dict()
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

    async def is_current_round(self, session: AsyncSession, round_id: int) -> bool:
        """
        Checks if the specified mentorship round is currently active based on its timeline.

        A round is considered active if the current date falls between its start
        (match_notification_at, falling back to promotion_start_at) and
        meetings_completion_deadline_at (inclusive).

        Args:
            session (AsyncSession): Active database async session.
            round_id (int): The unique identifier of the mentorship round to check.

        Returns:
            bool: True if the round is currently active, False otherwise.

        Raises:
            ValueError: If the round is not found or the required timeline fields
            are missing in the round's description.
        """
        round_entity = await self.mentorship_round_repository.get_by_round_id(
            session, round_id
        )
        if not round_entity:
            raise ValueError("Round with given ID does not exist.")

        desc = round_entity.description or {}
        start_raw = desc.get("match_notification_at") or desc.get("promotion_start_at")
        end_raw = desc.get("meetings_completion_deadline_at")

        if not start_raw or not end_raw:
            raise ValueError("Can't determine round status due to incomplete timeline.")

        today = datetime.now(timezone.utc).date()
        return date.fromisoformat(start_raw) <= today <= date.fromisoformat(end_raw)
