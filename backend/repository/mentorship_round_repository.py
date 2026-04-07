from backend.entity.mentorship_round_entity import MentorshipRoundEntity
from datetime import datetime, timezone
from sqlalchemy import Date, cast, select
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

    async def get_by_round_id(
        self, session: AsyncSession, round_id: int
    ) -> MentorshipRoundEntity | None:
        """
        Retrieve a mentorship round entity by its round ID.

        Args:
            session (AsyncSession): The active async database session.
            round_id (int): The ID of the mentorship round to retrieve.

        Returns:
            MentorshipRoundEntity | None: The mentorship round entity, otherwise None.
        """
        if not round_id:
            return None

        result = await session.execute(
            select(MentorshipRoundEntity).where(
                MentorshipRoundEntity.round_id == round_id,
            )
        )

        return result.scalar_one_or_none()

    async def get_running_round_id(self, session: AsyncSession) -> int | None:
        """
        Return the round_id of the round whose meeting window is currently open, or None.

        The meeting window spans from match_notification_at through
        meetings_completion_deadline_at (inclusive), stored as ISO date strings in
        the description JSONB field.

        Args:
            session (AsyncSession): The active async database session.

        Returns: The running round ID or None.
        """
        today = datetime.now(timezone.utc).date()
        result = await session.execute(
            select(MentorshipRoundEntity.round_id).where(
                cast(
                    MentorshipRoundEntity.description["match_notification_at"].astext,
                    Date,
                )
                <= today,
                cast(
                    MentorshipRoundEntity.description[
                        "meetings_completion_deadline_at"
                    ].astext,
                    Date,
                )
                >= today,
            )
        )
        return result.scalars().first()

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
