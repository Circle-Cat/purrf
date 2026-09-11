from datetime import datetime

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.recruiting_enums import NotificationStatus
from backend.entity.notification_entity import NotificationEntity


class NotificationRepository:
    """Database operations for NotificationEntity (append-only; dismissing marks the row).

    Dismissing sets ``dismissed_at`` rather than removing the row: the same
    row carries the delivery state, so deleting it would drop a mail that had
    not gone out and erase the record of one that had.

    The bell reads -- ``list_by_user`` and ``count_by_user`` -- are scoped to
    undismissed rows. The delivery ones below are not, and must not be:
    dismissing takes the row off the bell, not out of the mail queue, so a
    notification dismissed before its email went out still gets sent.
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

    async def get_by_id(
        self, session: AsyncSession, notification_id: int
    ) -> NotificationEntity | None:
        """One notification by its primary key, dismissed or not.

        Args:
            session (AsyncSession): The active async database session.
            notification_id (int): The row wanted.

        Returns:
            NotificationEntity | None: The row, or None if there is no such id.
        """
        return await session.get(NotificationEntity, notification_id)

    async def claim_for_sending(
        self,
        session: AsyncSession,
        notification_id: int,
        *,
        now: datetime,
        stale_before: datetime,
    ) -> bool:
        """Take the row for sending, from PENDING or from a claim gone stale.

        The guard is the whole point: the WHERE clause and the write are one
        statement, so two senders racing on the same row cannot both come
        away believing they own it. Whoever loses matches no row.

        Args:
            session (AsyncSession): The active async database session.
            notification_id (int): The row to claim.
            now (datetime): Stamped as the claim time.
            stale_before (datetime): A SENDING claim older than this is
                treated as abandoned and may be retaken. The caller decides
                how long that is.

        Returns:
            bool: True when this caller now owns the send. False means
                somebody else holds it, already sent it, or settled it.
        """
        result = await session.execute(
            update(NotificationEntity)
            .where(
                NotificationEntity.notification_id == notification_id,
                or_(
                    NotificationEntity.status == NotificationStatus.PENDING,
                    (NotificationEntity.status == NotificationStatus.SENDING)
                    & (NotificationEntity.claimed_at < stale_before),
                ),
            )
            .values(status=NotificationStatus.SENDING, claimed_at=now)
        )
        return result.rowcount == 1

    async def set_status(
        self,
        session: AsyncSession,
        notification_id: int,
        status: NotificationStatus,
    ) -> None:
        """Write the row's delivery status and drop whatever claim it held.

        The claim is cleared with every status, released or terminal. A row
        put back to PENDING while still carrying a ``claimed_at`` would read
        to ``claim_for_sending`` as live and never be retried.

        Args:
            session (AsyncSession): The active async database session.
            notification_id (int): The row to write.
            status (NotificationStatus): The status to write.
        """
        await session.execute(
            update(NotificationEntity)
            .where(NotificationEntity.notification_id == notification_id)
            .values(status=status, claimed_at=None)
        )

    async def list_pending_ids_created_before(
        self, session: AsyncSession, cutoff: datetime, limit: int
    ) -> list[int]:
        """Ids of PENDING rows older than ``cutoff``, oldest first.

        Args:
            session (AsyncSession): The active async database session.
            cutoff (datetime): Only rows created strictly before this.
            limit (int): Most ids to return in one pass.

        Returns:
            list[int]: Notification ids, oldest first. Empty when none match.
        """
        result = await session.execute(
            select(NotificationEntity.notification_id)
            .where(
                NotificationEntity.status == NotificationStatus.PENDING,
                NotificationEntity.created_at < cutoff,
            )
            .order_by(NotificationEntity.created_at.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

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
