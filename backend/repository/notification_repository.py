from sqlalchemy import delete, func, select, update
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

    async def claim_unemailed(
        self, session: AsyncSession, limit: int
    ) -> list[NotificationEntity]:
        """Lock and return up to ``limit`` notifications still awaiting email.

        Oldest first, so a backlog drains in the order it accrued. The rows
        are locked ``FOR UPDATE SKIP LOCKED`` and stay locked until the
        caller's transaction ends: a second worker (a replica, or an
        overlapping pass) skips them rather than blocking on them or
        double-sending. The deployment runs a single replica today, so this
        costs nothing now and is what keeps scaling to two from silently
        emailing everyone twice.

        Args:
            session (AsyncSession): Active database async session, inside a
                transaction that must stay open until the rows are stamped.
            limit (int): Maximum rows to claim in one pass.

        Returns:
            list[NotificationEntity]: The claimed rows, oldest first.
        """
        result = await session.execute(
            select(NotificationEntity)
            .where(NotificationEntity.email_sent_at.is_(None))
            .order_by(NotificationEntity.created_at.asc())
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        return list(result.scalars().all())

    async def mark_emailed(
        self, session: AsyncSession, notification_ids: list[int], sent_at
    ) -> None:
        """Stamp ``email_sent_at`` on the given rows.

        Called for every claimed row, delivered or not -- see
        :class:`NotificationEntity` on why an undeliverable row is stamped
        rather than left for the next pass.

        Args:
            session (AsyncSession): Active database async session.
            notification_ids (list[int]): Rows to stamp; empty is a no-op.
            sent_at (datetime): The stamp value.
        """
        if not notification_ids:
            return
        await session.execute(
            update(NotificationEntity)
            .where(NotificationEntity.notification_id.in_(notification_ids))
            .values(email_sent_at=sent_at)
        )

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
