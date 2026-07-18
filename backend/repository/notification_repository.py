from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.entity.notification_entity import NotificationEntity


class NotificationRepository:
    """Database operations for NotificationEntity (append-only; dismissing deletes the row)."""

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

    async def count_by_user(self, session: AsyncSession, user_id: int) -> int:
        """Count one user's notifications (all pending -- dismissed rows are deleted)."""
        result = await session.execute(
            select(func.count())
            .select_from(NotificationEntity)
            .where(NotificationEntity.user_id == user_id)
        )
        return result.scalar_one()

    async def delete_by_id(
        self, session: AsyncSession, notification_id: int, user_id: int
    ) -> bool:
        """Delete one notification, only if it belongs to user_id.

        Returns False (no-op) if the notification is missing or owned by a
        different user -- the caller must not learn anything about another
        user's notification ids via this call's return value.
        """
        entity = await session.get(NotificationEntity, notification_id)
        if entity is None or entity.user_id != user_id:
            return False
        await session.delete(entity)
        await session.flush()
        return True

    async def delete_all_by_user(self, session: AsyncSession, user_id: int) -> None:
        """Delete every notification for user_id."""
        await session.execute(
            delete(NotificationEntity).where(NotificationEntity.user_id == user_id)
        )
        await session.flush()
