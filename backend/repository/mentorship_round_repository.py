from backend.entity.mentorship_round_entity import MentorshipRoundEntity
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class MentorshipRoundRepository:
    """
    Repository for handling database operations related to MentorshipRoundEntity.
    """

    async def get_all_rounds(
        self, session: AsyncSession
    ) -> list[MentorshipRoundEntity]:
        """
        Retrieve all mentorship round entities.

        This method expects an externally managed AsyncSession, typically provided
        by the service layer within a transactional context.

        Args:
            session (AsyncSession): The active async database session.

        Returns:
            list[MentorshipRoundEntity]: A list of all matching MentorshipRound.
                                        Returns an empty list if no records are found.
        """
        result = await session.execute(select(MentorshipRoundEntity))

        return result.scalars().all()

    async def upsert_round(
        self, session: AsyncSession, entity: MentorshipRoundEntity
    ) -> MentorshipRoundEntity:
        """
        Inserts or updates a MentorshipRoundEntity object in the database.

        This method using session.merge() handles data persistence, it will
        update the entity if the primary key exists, or inserts it otherwise

        Args:
            session (AsyncSession): The active async database session.
            entity: The MentorshipRound object containing the round data.

        Returns:
            MentorshipRound: The entity object synchronized with the database, reflecting
            the latest state, generated keys, and default values.
        """
        merged_entity = await session.merge(entity)
        await session.flush()

        return merged_entity
