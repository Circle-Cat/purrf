from datetime import datetime, timedelta, timezone
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.recruiting_enums import NotificationStatus

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

    def __init__(self, logger, email_service, notification_repository):
        """
        Args:
            logger: Logger instance.
            email_service: Object with ``async send(session, notification)``,
                raising LookupError when the recipient can never be emailed.
            notification_repository (NotificationRepository): Owns every read
                and write of the notification row, the claim included.
        """
        self.logger = logger
        self.email_service = email_service
        self.notification_repository = notification_repository

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
        notification = await self.notification_repository.get_by_id(
            session, notification_id
        )
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
        """Take the row and commit the claim, so other senders can see it.

        How long a claim may go unfinished before another sender may retake
        it is this service's decision, not the repository's -- CLAIM_TIMEOUT
        is the ack deadline of the subscription that drives delivery.

        Returns:
            bool: True when this caller owns the send. False means somebody
                else already sent it, is sending it, or settled it.
        """
        claimed = await self.notification_repository.claim_for_sending(
            session,
            notification_id,
            now=now,
            stale_before=now - CLAIM_TIMEOUT,
        )
        await session.commit()
        return claimed

    async def _settle(
        self, session: AsyncSession, notification_id: int, status: NotificationStatus
    ) -> None:
        """Write the terminal (or released) status and commit it.

        The commit belongs here rather than in the repository: delivery is
        driven by a Pub/Sub push and owns its transaction, while every other
        caller of that repository runs inside somebody else's.
        """
        await self.notification_repository.set_status(session, notification_id, status)
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
        return await self.notification_repository.list_pending_ids_created_before(
            session, cutoff=cutoff, limit=limit
        )
