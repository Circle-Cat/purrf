from datetime import datetime, timedelta, timezone
from enum import Enum

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.recruiting_enums import NotificationStatus
from backend.entity.notification_entity import NotificationEntity

EXPIRY = timedelta(hours=24)
CLAIM_TIMEOUT = timedelta(minutes=10)


class DeliveryOutcome(Enum):
    """What the caller should tell Pub/Sub.

    ACKED means "do not send this message again" -- including every case
    where retrying could not produce a different result. RETRY is reserved
    for "not right now, but maybe shortly", because Pub/Sub redelivers a
    non-2xx with backoff until the message expires, up to seven days.
    """

    ACKED = "acked"
    RETRY = "retry"


class DeliveryService:
    """Turns one notification row into one email, exactly once."""

    def __init__(self, logger, email_service):
        """
        Args:
            logger: Logger instance.
            email_service: Object with ``async send(session, notification)``,
                raising LookupError when the recipient can never be emailed.
        """
        self.logger = logger
        self.email_service = email_service

    async def deliver(
        self, session: AsyncSession, notification_id: int
    ) -> DeliveryOutcome:
        """Claim, render and send one notification's email.

        Args:
            session (AsyncSession): Active database async session.
            notification_id (int): Row to deliver.

        Returns:
            DeliveryOutcome: ACKED when Pub/Sub should stop, RETRY when it
                should back off and try again.
        """
        notification = await session.get(NotificationEntity, notification_id)
        if notification is None:
            self.logger.info("[Delivery] %s does not exist; acking", notification_id)
            return DeliveryOutcome.ACKED

        now = datetime.now(timezone.utc)
        if now - notification.created_at > EXPIRY:
            await self._settle(session, notification_id, NotificationStatus.EXPIRED)
            return DeliveryOutcome.ACKED

        if not await self._claim(session, notification_id, now):
            return DeliveryOutcome.ACKED

        try:
            await self.email_service.send(session, notification)
        except LookupError:
            self.logger.warning(
                "[Delivery] %s can never be emailed; marking failed", notification_id
            )
            await self._settle(session, notification_id, NotificationStatus.FAILED)
            return DeliveryOutcome.ACKED
        except Exception:
            self.logger.exception("[Delivery] %s failed transiently", notification_id)
            await self._settle(session, notification_id, NotificationStatus.PENDING)
            return DeliveryOutcome.RETRY

        await self._settle(session, notification_id, NotificationStatus.SENT)
        return DeliveryOutcome.ACKED

    async def _claim(
        self, session: AsyncSession, notification_id: int, now: datetime
    ) -> bool:
        """Take the row from PENDING, or from a SENDING claim older than the timeout.

        Returns:
            bool: True when this caller owns the send. False means somebody
                else already sent it, is sending it, or settled it.
        """
        result = await session.execute(
            update(NotificationEntity)
            .where(
                NotificationEntity.notification_id == notification_id,
                or_(
                    NotificationEntity.status == NotificationStatus.PENDING,
                    (NotificationEntity.status == NotificationStatus.SENDING)
                    & (NotificationEntity.claimed_at < now - CLAIM_TIMEOUT),
                ),
            )
            .values(status=NotificationStatus.SENDING, claimed_at=now)
        )
        await session.commit()
        return result.rowcount == 1

    async def _settle(
        self, session: AsyncSession, notification_id: int, status: NotificationStatus
    ) -> None:
        """Write the terminal (or released) status and commit it."""
        await session.execute(
            update(NotificationEntity)
            .where(NotificationEntity.notification_id == notification_id)
            .values(status=status, claimed_at=None)
        )
        await session.commit()

    async def sweep_stragglers(
        self, session: AsyncSession, limit: int = 20
    ) -> list[int]:
        """Return ids of PENDING rows old enough that their publish likely never landed.

        This is the only backstop for "the transaction committed but the
        publish did not". It rides along on real deliveries instead of a
        timer, which is the price of having no scheduled job.

        Args:
            session (AsyncSession): Active database async session.
            limit (int): Most ids to return in one pass.

        Returns:
            list[int]: Notification ids to republish, oldest first.
        """
        cutoff = datetime.now(timezone.utc) - CLAIM_TIMEOUT
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
