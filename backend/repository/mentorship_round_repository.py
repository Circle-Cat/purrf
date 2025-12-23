from backend.entity.mentorship_round_entity import MentorshipRoundEntity
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class MentorshipRoundRepository:
    """
    Repository for handling database operations related to MentorshipRoundRepository.
    """

    async def get_all_rounds(
        self, session: AsyncSession
    ) -> list[MentorshipRoundEntity] | None:
        """
        Retrieve all mentorship round entities.

        This method expects an externally managed AsyncSession, typically provided
        by the service layer within a transactional context.

        Args:
            session (AsyncSession): The active async database session.

        Returns:
            list[MentorshipRoundEntity]: A list of all matching MentorshipRound.
        """
        result = await session.execute(select(MentorshipRoundEntity))

        return result.scalars().all()
