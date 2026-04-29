from backend.entity.mentorship_round_entity import MentorshipRoundEntity
from backend.entity.mentorship_round_participants_entity import (
    MentorshipRoundParticipantsEntity,
)
from backend.common.mentorship_enums import ParticipantRole
from sqlalchemy import TIMESTAMP, Float, cast, func, select, and_
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

    async def get_recent_participant_by_user_id(
        self, session: AsyncSession, user_id: int
    ) -> MentorshipRoundParticipantsEntity | None:
        """
        Retrieve the most recent mentorship round participant for a user,
        ordered by the round's meetings_completion_deadline_at descending.

        Rounds without meetings_completion_deadline_at are skipped because
        their timeline is not finalized.

        Args:
            session (AsyncSession): The active async database session.
            user_id (int): User id.

        Returns:
            MentorshipRoundParticipantsEntity | None: The matching participant or None.
        """
        result = await session.execute(
            select(MentorshipRoundParticipantsEntity)
            .join(
                MentorshipRoundEntity,
                MentorshipRoundEntity.round_id
                == MentorshipRoundParticipantsEntity.round_id,
            )
            .where(
                MentorshipRoundParticipantsEntity.user_id == user_id,
                MentorshipRoundEntity.description[
                    "meetings_completion_deadline_at"
                ].astext.isnot(None),
            )
            .order_by(
                cast(
                    MentorshipRoundEntity.description[
                        "meetings_completion_deadline_at"
                    ].astext,
                    TIMESTAMP(timezone=True),
                ).desc()
            )
            .limit(1)
        )

        return result.scalars().one_or_none()

    async def get_average_program_rating_by_round_and_role(
        self,
        session: AsyncSession,
        round_id: int,
        role: ParticipantRole,
    ) -> float:
        """
        Compute the average program_rating for all participants in a round with a specific role.

        Args:
            session (AsyncSession): The active async database session.
            round_id (int): Mentorship round id.
            role (ParticipantRole): The participant role to filter by.

        Returns:
            float: The average program_rating.
        """
        result = await session.execute(
            select(
                func.avg(
                    cast(
                        MentorshipRoundParticipantsEntity.program_feedback[
                            "program_rating"
                        ].astext,
                        Float,
                    )
                )
            ).where(
                and_(
                    MentorshipRoundParticipantsEntity.round_id == round_id,
                    MentorshipRoundParticipantsEntity.participant_role == role,
                    MentorshipRoundParticipantsEntity.program_feedback[
                        "program_rating"
                    ].astext.isnot(None),
                )
            )
        )
        return result.scalar_one_or_none()

    async def upsert_participant(
        self, session: AsyncSession, entity: MentorshipRoundParticipantsEntity
    ) -> MentorshipRoundParticipantsEntity:
        """
        Inserts or updates a MentorshipRoundParticipantsEntity in the database.

        Args:
            session (AsyncSession): Active async database session.
            entity (MentorshipRoundParticipantsEntity): The entity containing
                mentorship round participation data.

        Returns:
            MentorshipRoundParticipantsEntity: The merged entity instance synchronized with the session.
        """
        merged_entity = await session.merge(entity)
        await session.flush()

        return merged_entity
