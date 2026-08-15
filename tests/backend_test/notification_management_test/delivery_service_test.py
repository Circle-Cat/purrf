from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

from backend.common.mentorship_enums import CommunicationMethod
from backend.common.recruiting_enums import NotificationStatus
from backend.entity.event_entity import EventEntity
from backend.entity.notification_entity import NotificationEntity
from backend.entity.users_entity import UsersEntity
from backend.notification_management.delivery_service import (
    DeliveryOutcome,
    DeliveryService,
)
from tests.backend_test.repository_test.base_repository_test_lib import (
    BaseRepositoryTestLib,
)


def _make_user() -> UsersEntity:
    """Build a minimal, unsaved user row to own a notification.

    ``NotificationEntity.user_id`` is a real FK against the shared CI
    database, so a hardcoded literal id (as the brief's phantom
    ``make_notification`` helper used) risks either an FK violation or a
    collision with a concurrent test run -- same gotcha Task 3 hit and
    documented.
    """
    return UsersEntity(
        first_name="U",
        last_name="Ser",
        timezone="America/Los_Angeles",
        timezone_updated_at=datetime.now(timezone.utc),
        communication_channel=CommunicationMethod.EMAIL,
        is_active=True,
        updated_timestamp=datetime.now(timezone.utc),
    )


class DeliveryServiceTest(BaseRepositoryTestLib):
    """DB-backed in place of the brief's phantom ``tests/backend_test/helpers``
    module (does not exist in this repo -- see Task 3's report). Uses the
    established ``BaseRepositoryTestLib`` pattern instead: per-test rollback
    against the shared CI database, with a private helper method standing in
    for the missing fixture."""

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.email = AsyncMock()
        self.logger = MagicMock()
        self.service = DeliveryService(logger=self.logger, email_service=self.email)

    async def _make_notification(
        self, *, status=None, claimed_at=None, created_at=None
    ) -> NotificationEntity:
        """A notification owned by a freshly created user, PENDING unless overridden."""
        recipient = _make_user()
        await self.insert_entities([recipient])
        event = EventEntity(
            subject_type="application",
            subject_id=1,
            actor_id=recipient.user_id,
            event_type="demo.thing",
        )
        await self.insert_entities([event])
        kwargs = {
            "user_id": recipient.user_id,
            "event_id": event.event_id,
            "created_at": created_at or datetime.now(timezone.utc),
        }
        if status is not None:
            kwargs["status"] = status
        if claimed_at is not None:
            kwargs["claimed_at"] = claimed_at
        notification = NotificationEntity(**kwargs)
        await self.insert_entities([notification])
        return notification

    async def test_delivering_twice_sends_exactly_one_email(self):
        notification = await self._make_notification()

        first = await self.service.deliver(self.session, notification.notification_id)
        second = await self.service.deliver(self.session, notification.notification_id)

        self.assertEqual(first, DeliveryOutcome.ACKED)
        self.assertEqual(second, DeliveryOutcome.ACKED)
        self.assertEqual(self.email.send.await_count, 1)

    async def test_unknown_id_is_acked_not_retried(self):
        """Acking a message for a row that is not there ends it silently, so
        the log line is the only record that the id was ever pushed."""
        outcome = await self.service.deliver(self.session, 999_999)

        self.assertEqual(outcome, DeliveryOutcome.ACKED)
        self.email.send.assert_not_awaited()
        self.logger.info.assert_called_once()

    async def test_a_stale_claim_may_be_retaken(self):
        """A process that died between claiming and sending must not strand the row."""
        notification = await self._make_notification(
            status=NotificationStatus.SENDING,
            claimed_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )

        outcome = await self.service.deliver(self.session, notification.notification_id)

        self.assertEqual(outcome, DeliveryOutcome.ACKED)
        self.assertEqual(self.email.send.await_count, 1)

    async def test_a_fresh_claim_is_left_alone(self):
        notification = await self._make_notification(
            status=NotificationStatus.SENDING,
            claimed_at=datetime.now(timezone.utc),
        )

        outcome = await self.service.deliver(self.session, notification.notification_id)

        self.assertEqual(outcome, DeliveryOutcome.ACKED)
        self.email.send.assert_not_awaited()

    async def test_past_its_shelf_life_it_expires_instead_of_sending(self):
        notification = await self._make_notification(
            created_at=datetime.now(timezone.utc) - timedelta(hours=25),
        )

        outcome = await self.service.deliver(self.session, notification.notification_id)

        self.assertEqual(outcome, DeliveryOutcome.ACKED)
        self.assertEqual(notification.status, NotificationStatus.EXPIRED)
        self.email.send.assert_not_awaited()

    async def test_a_recipient_with_no_address_fails_permanently(self):
        self.email.send.side_effect = LookupError("no address on file")
        notification = await self._make_notification()

        outcome = await self.service.deliver(self.session, notification.notification_id)

        self.assertEqual(outcome, DeliveryOutcome.ACKED)
        self.assertEqual(notification.status, NotificationStatus.FAILED)
        self.logger.warning.assert_called_once()

    async def test_gmail_being_down_asks_for_a_retry(self):
        self.email.send.side_effect = RuntimeError("gmail 503")
        notification = await self._make_notification()

        outcome = await self.service.deliver(self.session, notification.notification_id)

        self.assertEqual(outcome, DeliveryOutcome.RETRY)
        self.assertEqual(notification.status, NotificationStatus.PENDING)
        self.logger.exception.assert_called_once()


if __name__ == "__main__":
    import unittest

    unittest.main()
