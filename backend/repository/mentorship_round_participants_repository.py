from backend.entity.mentorship_round_participants_entity import (
    MentorshipRoundParticipantsEntity,
)
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession


class MentorshipRoundParticipantsRepository:
    """
    Repository for handling database operations related to MentorshipRoundParticipantsEntity.
    """

    async def get_by_user_id_and_round_id(
        self, session: AsyncSession, user_id: int, round_id: int
    ) -> MentorshipRoundParticipantsEntity | None:
        """
        Retrieve a mentorship round participant by user_id and round_id.

        Args:
            session (AsyncSession): The active async database session.
            user_id (int): User id.
            round_id (int): Mentorship round id.

        Returns:
            MentorshipRoundParticipantsEntity | None: The matching participant or None.
        """
        result = await session.execute(
            select(MentorshipRoundParticipantsEntity).where(
                and_(
                    MentorshipRoundParticipantsEntity.user_id == user_id,
                    MentorshipRoundParticipantsEntity.round_id == round_id,
                )
            )
        )

        return result.scalars().one_or_none()
