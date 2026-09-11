from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.entity.event_entity import EventEntity


class EventRepository:
    """Reads for the domain-neutral event log.

    Writing is not here: ``record_event`` adds the row and fans it out to
    recipients in one step, so a write that bypassed it would record what
    happened while telling nobody.
    """

    async def get_by_id(
        self, session: AsyncSession, event_id: int
    ) -> EventEntity | None:
        """One event by its primary key.

        Answers with None rather than raising, because the two callers
        disagree about whether a missing event is possible: the email side
        leans on ``notification.event_id`` being NOT NULL and cascading, the
        bell side renders empty display fields instead of failing a whole
        list for one row.

        Args:
            session (AsyncSession): Active database async session.
            event_id (int): The event wanted.

        Returns:
            EventEntity | None: The event, or None if there is no such id.
        """
        return await session.get(EventEntity, event_id)

    async def list_by_subject(
        self, session: AsyncSession, subject_type: str, subject_id: int
    ) -> list[EventEntity]:
        """Every event about one subject, newest first.

        Args:
            session (AsyncSession): Active database async session.
            subject_type (str): What the events are about, e.g. ``"application"``.
            subject_id (int): Primary key of that subject.

        Returns:
            list[EventEntity]: Newest first, falling back to ``event_id``
                descending to break ties between events written inside the
                same timestamp tick -- without it, the several events one
                request can record would come back in an arbitrary order.
        """
        result = await session.execute(
            select(EventEntity)
            .where(
                EventEntity.subject_type == subject_type,
                EventEntity.subject_id == subject_id,
            )
            .order_by(EventEntity.created_at.desc(), EventEntity.event_id.desc())
        )
        return list(result.scalars().all())
