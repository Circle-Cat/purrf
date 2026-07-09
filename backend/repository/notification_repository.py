from datetime import datetime, timezone

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.entity.notification_entity import NotificationEntity


class NotificationRepository:
    """Database operations for NotificationEntity (append-only, read_at is the only mutation)."""

    async def create(
        self, session: AsyncSession, entity: NotificationEntity
    ) -> NotificationEntity:
        """Insert a notification and flush so its notification_id is populated."""
        session.add(entity)
        await session.flush()
        return entity

    async def list_by_user(
        self,
        session: AsyncSession,
        user_id: int,
        limit: int = 20,
        offset: int = 0,
    ) -> list[NotificationEntity]:
        """List one user's notifications, newest first."""
        result = await session.execute(
            select(NotificationEntity)
            .where(NotificationEntity.user_id == user_id)
            .order_by(
                NotificationEntity.created_at.desc(),
                NotificationEntity.notification_id.desc(),
            )
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def count_unread(self, session: AsyncSession, user_id: int) -> int:
        """Count one user's notifications with read_at still null."""
        result = await session.execute(
            select(func.count())
            .select_from(NotificationEntity)
            .where(
                NotificationEntity.user_id == user_id,
                NotificationEntity.read_at.is_(None),
            )
        )
        return result.scalar_one()

    async def mark_read(
        self, session: AsyncSession, notification_id: int, user_id: int
    ) -> NotificationEntity | None:
        """Set read_at on one notification, only if it belongs to user_id.

        Returns None (no-op) if the notification is missing or owned by a
        different user -- the caller must not learn anything about another
        user's notification ids via this call's return value.
        """
        entity = await session.get(NotificationEntity, notification_id)
        if entity is None or entity.user_id != user_id:
            return None
        if entity.read_at is None:
            entity.read_at = datetime.now(timezone.utc)
            await session.flush()
        return entity

    async def mark_all_read(self, session: AsyncSession, user_id: int) -> None:
        """Set read_at on every currently-unread notification for user_id."""
        await session.execute(
            update(NotificationEntity)
            .where(
                NotificationEntity.user_id == user_id,
                NotificationEntity.read_at.is_(None),
            )
            .values(read_at=func.now())
        )
        await session.flush()
