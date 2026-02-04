from backend.entity.mentorship_pairs_entity import MentorshipPairsEntity
from sqlalchemy import select, or_, case
from sqlalchemy.ext.asyncio import AsyncSession


class MentorshipPairsRepository:
    """
    Repository for handling database operations related to MentorshipPairsEntity.
    """

    async def get_all_partner_ids(
        self, session: AsyncSession, user_id: int
    ) -> list[int]:
        """
        Retrieve a list of unique partner IDs (mentors or mentees) for a given user ID.

        This method identifies the user's role in each relationship:
        - If the user is the mentor, it returns the associated mentee's ID.
        - If the user is the mentee, it returns the associated mentor's ID.

        Args:
            session (AsyncSession): The active async database session.
            user_id (int): The ID of the user whose partners are being retrieved.

        Returns:
            list[int]: A list of unique partner IDs. Returns an empty list if
                    no partners are found or user_id is invalid.
        """
        if not user_id:
            return []

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

    async def get_partner_ids_by_user_and_round(
        self, session: AsyncSession, user_id: int, round_id: int
    ) -> list[int]:
        """
        Retrieve a list of unique partner IDs (mentors or mentees) for a given user ID
        within a specific mentorship round.

        This method identifies the user's role in each relationship for the given round:
        - If the user is the mentor, it returns the associated mentee's ID.
        - If the user is the mentee, it returns the associated mentor's ID.

        Args:
            session (AsyncSession): The active async database session.
            user_id (int): The ID of the user whose partners are being retrieved.
            round_id (int): The ID of the mentorship round to filter by.

        Returns:
            list[int]: A list of unique partner IDs whthin the specific round. Returns
                    an empty list if no partners are found or user_id/round_id is invalid.
        """
        if not user_id or not round_id:
            return []

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
                ),
                MentorshipPairsEntity.round_id == round_id,
            )
            .distinct()
        )

        return result.scalars().all()

    async def upsert_pairs(
        self, session: AsyncSession, entity: MentorshipPairsEntity
    ) -> MentorshipPairsEntity:
        """
        Inserts or updates a MentorshipPairsEntity in the database.

        Args:
            session (AsyncSession): Active async database session.
            entity (MentorshipPairsEntity): The entity containing pairs data.

        Returns:
            MentorshipPairsEntity: The merged entity instance synchronized with the session.
        """
        merged_entity = await session.merge(entity)
        await session.flush()

        return merged_entity
