from datetime import datetime, timezone
from unittest.mock import AsyncMock

from backend.common.mentorship_enums import CommunicationMethod
from backend.entity.event_entity import EventEntity
from backend.entity.notification_entity import NotificationEntity
from backend.entity.users_entity import UsersEntity
from backend.notification_management.notification_event_email_service import (
    NotificationEventEmailService,
)
from tests.backend_test.repository_test.base_repository_test_lib import (
    BaseRepositoryTestLib,
)


def _make_user() -> UsersEntity:
    return UsersEntity(
        first_name="U",
        last_name="Ser",
        timezone="America/Los_Angeles",
        timezone_updated_at=datetime.now(timezone.utc),
        communication_channel=CommunicationMethod.EMAIL,
        is_active=True,
        updated_timestamp=datetime.now(timezone.utc),
    )


class NotificationEventEmailServiceTest(BaseRepositoryTestLib):
    async def _make_notification(self):
        """A notification for a fresh recipient, pointing at a fresh event."""
        actor = _make_user()
        recipient = _make_user()
        await self.insert_entities([actor, recipient])
        event = EventEntity(
            subject_type="application",
            subject_id=1,
            actor_id=actor.user_id,
            event_type="demo.thing",
        )
        await self.insert_entities([event])
        notification = NotificationEntity(
            user_id=recipient.user_id, event_id=event.event_id
        )
        await self.insert_entities([notification])
        return notification

    async def test_no_address_on_file_raises_lookup_error(self):
        notification = await self._make_notification()
        user_emails_repository = AsyncMock()
        user_emails_repository.get_contact_email.return_value = None
        render = AsyncMock(return_value=("subject", "body"))
        service = NotificationEventEmailService(
            user_emails_repository=user_emails_repository,
            email_service=AsyncMock(),
            render=render,
        )

        with self.assertRaises(LookupError):
            await service.send(self.session, notification)

    async def test_transport_failure_raises_runtime_error(self):
        notification = await self._make_notification()
        user_emails_repository = AsyncMock()
        user_emails_repository.get_contact_email.return_value = "person@example.com"
        email_service = AsyncMock()
        email_service.send.return_value = False
        render = AsyncMock(return_value=("subject", "body"))
        service = NotificationEventEmailService(
            user_emails_repository=user_emails_repository,
            email_service=email_service,
            render=render,
        )

        with self.assertRaises(RuntimeError):
            await service.send(self.session, notification)

    async def test_happy_path_sends_the_rendered_email_to_the_resolved_address(self):
        notification = await self._make_notification()
        user_emails_repository = AsyncMock()
        user_emails_repository.get_contact_email.return_value = "person@example.com"
        email_service = AsyncMock()
        email_service.send.return_value = True
        render = AsyncMock(return_value=("the subject", "<p>the body</p>"))
        service = NotificationEventEmailService(
            user_emails_repository=user_emails_repository,
            email_service=email_service,
            render=render,
        )

        await service.send(self.session, notification)

        email_service.send.assert_awaited_once_with(
            "person@example.com", "the subject", "<p>the body</p>"
        )


if __name__ == "__main__":
    import unittest

    unittest.main()
