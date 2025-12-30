from backend.entity.mentorship_pairs_entity import MentorshipPairsEntity
from sqlalchemy import select, or_, case
from sqlalchemy.ext.asyncio import AsyncSession


class MentorshipPairsRepository:
    """
    Repository for handling database operations related to MentorshipPairsEntity.
    """

    async def get_pairs_by_users_id(
        self, session: AsyncSession, user_id: int
    ) -> list[int] | None:
        """
        Retrieve a list of unique partner IDs (mentors or mentees) for a given user ID.

        This method identifies the user's role in each relationship:
        - If the user is the mentor, it returns the associated mentee's ID.
        - If the user is the mentee, it returns the associated mentor's ID.

        Args:
            session (AsyncSession): The active async database session.
            user_id (int): The ID of the user whose partners are being retrieved.

        Returns:
            list[int] | None: A list of unique partner IDs, or None if user_id is empty.
        """
        if not user_id:
            return None

        partner_id_case = case(
            (
                MentorshipPairsEntity.mentor_id == user_id,
                MentorshipPairsEntity.mentee_id,
            ),
            else_=MentorshipPairsEntity.mentor_id,
        ).label("partner_id")

        result = await session.execute(
            select(partner_id_case)
            .where(
                or_(
                    MentorshipPairsEntity.mentor_id == user_id,
                    MentorshipPairsEntity.mentee_id == user_id,
                )
            )
            .distinct()
        )

        return result.scalars().all()
