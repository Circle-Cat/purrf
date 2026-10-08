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

    async def get_by_ids(
        self, session: AsyncSession, event_ids: list[int]
    ) -> list[EventEntity]:
        """The events with these ids, in no particular order.

        Ids with no event are left out rather than answered with None, for
        the same reason ``get_by_id`` does not raise.

        Args:
            session (AsyncSession): Active database async session.
            event_ids (list[int]): The events wanted.

        Returns:
            list[EventEntity]: The events found; empty, without a query, for
                no ids.
        """
        if not event_ids:
            return []
        result = await session.execute(
            select(EventEntity).where(EventEntity.event_id.in_(event_ids))
        )
        return list(result.scalars().all())

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

    async def latest_by_subjects(
        self,
        session: AsyncSession,
        subject_type: str,
        event_type: str,
        subject_ids: list[int],
    ) -> dict[int, EventEntity]:
        """The newest event of one type for each of several subjects.

        Args:
            session (AsyncSession): Active database async session.
            subject_type (str): What the events are about.
            event_type (str): The event type wanted.
            subject_ids (list[int]): The subjects.

        Returns:
            dict[int, EventEntity]: Keyed by subject id; subjects with no such
                event are absent. Ties on ``created_at`` go to the larger
                ``event_id``. Empty, without a query, for no ids.
        """
        if not subject_ids:
            return {}
        result = await session.execute(
            select(EventEntity)
            .where(
                EventEntity.subject_type == subject_type,
                EventEntity.event_type == event_type,
                EventEntity.subject_id.in_(subject_ids),
            )
            .order_by(
                EventEntity.subject_id,
                EventEntity.created_at.desc(),
                EventEntity.event_id.desc(),
            )
            .distinct(EventEntity.subject_id)
        )
        return {event.subject_id: event for event in result.scalars().all()}
