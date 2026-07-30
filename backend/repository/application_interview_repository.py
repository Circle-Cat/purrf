from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.recruiting_enums import ApplicationStage
from backend.entity.application_interview_entity import ApplicationInterviewEntity


class ApplicationInterviewRepository:
    """Data access for scheduled interview meetings."""

    async def get(
        self,
        session: AsyncSession,
        application_id: int,
        stage: ApplicationStage,
        round: int,
    ) -> ApplicationInterviewEntity | None:
        """The meeting booked for one application's stage+round, if any.

        Args:
            session (AsyncSession): The active DB session.
            application_id (int): The application.
            stage (ApplicationStage): The stage.
            round (int): The round within that stage.

        Returns:
            ApplicationInterviewEntity | None: The row, or None when nothing
                is booked for that round.
        """
        result = await session.execute(
            select(ApplicationInterviewEntity).where(
                ApplicationInterviewEntity.application_id == application_id,
                ApplicationInterviewEntity.stage == stage,
                ApplicationInterviewEntity.round == round,
            )
        )
        return result.scalars().first()

    async def create(
        self,
        session: AsyncSession,
        *,
        application_id: int,
        stage: ApplicationStage,
        round: int,
        google_event_id: str,
        meet_link: str | None,
        start_at,
        end_at,
        scheduled_by: int,
    ) -> ApplicationInterviewEntity:
        """Record a meeting Google has already created.

        Called only after the Calendar insert succeeds, so a failed booking
        never leaves a phantom row.

        Args:
            session (AsyncSession): The active DB session.
            application_id (int): The application.
            stage (ApplicationStage): The stage being interviewed.
            round (int): The round within that stage.
            google_event_id (str): The Calendar event id.
            meet_link (str | None): The Meet URL, when Google returned one.
            start_at (datetime): Start, tz-aware UTC.
            end_at (datetime): End, tz-aware UTC.
            scheduled_by (int): The recruiter who booked it.

        Returns:
            ApplicationInterviewEntity: The persisted row.
        """
        entity = ApplicationInterviewEntity(
            application_id=application_id,
            stage=stage,
            round=round,
            google_event_id=google_event_id,
            meet_link=meet_link,
            start_at=start_at,
            end_at=end_at,
            scheduled_by=scheduled_by,
        )
        session.add(entity)
        await session.flush()
        return entity

    async def update_schedule(
        self,
        session: AsyncSession,
        entity: ApplicationInterviewEntity,
        *,
        start_at,
        end_at,
        meet_link: str | None,
    ) -> ApplicationInterviewEntity:
        """Apply a reschedule to an existing row.

        ``scheduled_by`` and ``google_event_id`` are deliberately not
        parameters: the event is patched in place, and the recruiter on the
        invite stays whoever first booked it.

        Args:
            session (AsyncSession): The active DB session.
            entity (ApplicationInterviewEntity): The row to update.
            start_at (datetime): New start, tz-aware UTC.
            end_at (datetime): New end, tz-aware UTC.
            meet_link (str | None): The Meet URL from the patched event.

        Returns:
            ApplicationInterviewEntity: The updated row.
        """
        entity.start_at = start_at
        entity.end_at = end_at
        entity.meet_link = meet_link
        session.add(entity)
        await session.flush()
        return entity

    async def delete(
        self, session: AsyncSession, entity: ApplicationInterviewEntity
    ) -> None:
        """Remove a cancelled meeting's row.

        No tombstone: the ``interview_cancelled`` activity entry is the
        history, matching how reject/blacklist record theirs.

        Args:
            session (AsyncSession): The active DB session.
            entity (ApplicationInterviewEntity): The row to delete.

        Returns:
            None
        """
        await session.delete(entity)
        await session.flush()

    async def list_by_application_ids(
        self, session: AsyncSession, application_ids: list[int]
    ) -> list[ApplicationInterviewEntity]:
        """Every interview row for a batch of applications.

        Args:
            session (AsyncSession): The active DB session.
            application_ids (list[int]): The applications to fetch for.

        Returns:
            list[ApplicationInterviewEntity]: Unordered; empty for empty input
                (short-circuits without a query).
        """
        if not application_ids:
            return []
        result = await session.execute(
            select(ApplicationInterviewEntity).where(
                ApplicationInterviewEntity.application_id.in_(application_ids)
            )
        )
        return list(result.scalars().all())
