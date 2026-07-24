from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.entity.application_activity_entity import ApplicationActivityEntity


class ApplicationActivityRepository:
    """Database operations for ApplicationActivityEntity (append-only)."""

    async def create(
        self,
        session: AsyncSession,
        application_id: int,
        actor_id: int,
        event_type: str,
        details: dict | None = None,
        created_at: datetime | None = None,
    ) -> ApplicationActivityEntity:
        """Append one audit entry to an application's timeline.

        Args:
            session (AsyncSession): The active DB session.
            application_id (int): The application this event happened on.
            actor_id (int): The user who performed (or triggered) the action.
            event_type (str): One of the fixed event-type strings used by
                the callers in ``application_service.py``/``board_service.py``.
            details (dict | None): Event-specific payload; defaults to ``{}``.
            created_at (datetime | None): Real-world event time. When provided
                (e.g. a synced reply's receive time) it is stored verbatim so
                the timeline sorts by when the event actually happened; when
                ``None`` the server ``now()`` default applies.

        Returns:
            ApplicationActivityEntity: The created row.
        """
        entity = ApplicationActivityEntity(
            application_id=application_id,
            actor_id=actor_id,
            event_type=event_type,
            details=details or {},
        )
        if created_at is not None:
            entity.created_at = created_at
        session.add(entity)
        await session.flush()
        return entity

    async def list_by_application(
        self, session: AsyncSession, application_id: int
    ) -> list[ApplicationActivityEntity]:
        """Every audit entry for one application, newest first.

        Args:
            session (AsyncSession): The active DB session.
            application_id (int): The application to fetch history for.

        Returns:
            list[ApplicationActivityEntity]: Ordered by created_at descending,
                falling back to ``activity_id`` descending to break ties
                between events written within the same DB timestamp tick.
        """
        result = await session.execute(
            select(ApplicationActivityEntity)
            .where(ApplicationActivityEntity.application_id == application_id)
            .order_by(
                ApplicationActivityEntity.created_at.desc(),
                ApplicationActivityEntity.activity_id.desc(),
            )
        )
        return list(result.scalars().all())
