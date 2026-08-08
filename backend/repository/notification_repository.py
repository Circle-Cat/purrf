from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.entity.notification_entity import NotificationEntity


class NotificationRepository:
    """Database operations for NotificationEntity (append-only; dismissing marks the row).

    Dismissing sets ``dismissed_at`` rather than removing the row: the same
    row carries the delivery state, so deleting it would drop a mail that had
    not gone out and erase the record of one that had. Every read here is
    scoped to undismissed rows.
    """

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
        """List one user's undismissed notifications, newest first."""
        result = await session.execute(
            select(NotificationEntity)
            .where(
                NotificationEntity.user_id == user_id,
                NotificationEntity.dismissed_at.is_(None),
            )
            .order_by(
                NotificationEntity.created_at.desc(),
                NotificationEntity.notification_id.desc(),
            )
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def count_by_user(self, session: AsyncSession, user_id: int) -> int:
        """Count one user's undismissed notifications."""
        result = await session.execute(
            select(func.count())
            .select_from(NotificationEntity)
            .where(
                NotificationEntity.user_id == user_id,
                NotificationEntity.dismissed_at.is_(None),
            )
        )
        return result.scalar_one()

    async def dismiss_by_id(
        self, session: AsyncSession, notification_id: int, user_id: int
    ) -> bool:
        """Mark one notification dismissed, only if it belongs to user_id.

        Returns False (no-op) if the notification is missing or owned by a
        different user -- the caller must not learn anything about another
        user's notification ids via this call's return value. Dismissing an
        already-dismissed row refreshes the timestamp and still returns True;
        the caller asked for it to be gone and it is.
        """
        result = await session.execute(
            update(NotificationEntity)
            .where(
                NotificationEntity.notification_id == notification_id,
                NotificationEntity.user_id == user_id,
            )
            .values(dismissed_at=func.now())
        )
        await session.flush()
        return result.rowcount > 0

    async def dismiss_all_by_user(self, session: AsyncSession, user_id: int) -> None:
        """Mark every one of user_id's undismissed notifications dismissed."""
        await session.execute(
            update(NotificationEntity)
            .where(
                NotificationEntity.user_id == user_id,
                NotificationEntity.dismissed_at.is_(None),
            )
            .values(dismissed_at=func.now())
        )
        await session.flush()
