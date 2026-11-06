import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock

from backend.common.mentorship_enums import CommunicationMethod
from backend.entity.event_entity import EventEntity
from backend.entity.notification_entity import NotificationEntity
from backend.entity.users_entity import UsersEntity
from backend.notification_management.notification_event_email_service import (
    NotificationEventEmailService,
    with_link,
)
from backend.repository.event_repository import EventRepository
from tests.backend_test.repository_test.base_repository_test_lib import (
    BaseRepositoryTestLib,
)


_FOOTER = (
    "<p>This is an automated message from Purrf. Replies to this address "
    "aren't monitored.</p>"
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
            event_repository=EventRepository(),
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
            event_repository=EventRepository(),
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
            event_repository=EventRepository(),
            render=render,
        )

        await service.send(self.session, notification)

        email_service.send.assert_awaited_once_with(
            "person@example.com", "the subject", "<p>the body</p>"
        )

    def _linked_service(
        self, email_service, link, app_origin="https://app.example.test/"
    ):
        user_emails_repository = AsyncMock()
        user_emails_repository.get_contact_email.return_value = "person@example.com"
        return NotificationEventEmailService(
            user_emails_repository=user_emails_repository,
            email_service=email_service,
            event_repository=EventRepository(),
            render=AsyncMock(return_value=("s", f"<p>body</p>{_FOOTER}")),
            link=link,
            app_origin=app_origin,
        )

    async def test_links_the_recipient_to_their_page_above_the_footer(self):
        notification = await self._make_notification()
        email_service = AsyncMock()
        email_service.send.return_value = True
        link = AsyncMock(return_value="/recruiting/applications/7?mode=evaluate")
        service = self._linked_service(email_service, link)

        await service.send(self.session, notification)

        args = link.await_args.args
        self.assertEqual(args[1].event_id, notification.event_id)
        self.assertEqual(args[2], notification.user_id)
        body = email_service.send.await_args.args[2]
        self.assertEqual(
            body,
            "<p>body</p>"
            '<p><a href="https://app.example.test/recruiting/applications/7'
            '?mode=evaluate">Open in Purrf</a></p>' + _FOOTER,
        )

    async def test_sends_without_a_link_when_there_is_no_page(self):
        notification = await self._make_notification()
        email_service = AsyncMock()
        email_service.send.return_value = True
        service = self._linked_service(email_service, AsyncMock(return_value=None))

        await service.send(self.session, notification)

        self.assertEqual(email_service.send.await_args.args[2], f"<p>body</p>{_FOOTER}")

    async def test_sends_without_a_link_when_no_app_origin_is_configured(self):
        notification = await self._make_notification()
        email_service = AsyncMock()
        email_service.send.return_value = True
        link = AsyncMock(return_value="/inbox")
        service = self._linked_service(email_service, link, app_origin=None)

        await service.send(self.session, notification)

        link.assert_not_awaited()
        self.assertEqual(email_service.send.await_args.args[2], f"<p>body</p>{_FOOTER}")


class WithLinkTest(unittest.TestCase):
    def test_appends_when_the_body_has_no_footer(self):
        self.assertEqual(
            with_link("<p>x</p>", "https://a.test/inbox"),
            '<p>x</p><p><a href="https://a.test/inbox">Open in Purrf</a></p>',
        )

    def test_escapes_the_url_for_the_attribute(self):
        self.assertIn(
            'href="https://a.test/inbox?service=mentorship&amp;x=&quot;y&quot;"',
            with_link("<p>x</p>", 'https://a.test/inbox?service=mentorship&x="y"'),
        )

    def test_goes_above_the_last_footer_only(self):
        body = f"<p>quoted: {_FOOTER}</p>{_FOOTER}"
        linked = with_link(body, "https://a.test/x")
        self.assertTrue(
            linked.endswith(
                f'<p><a href="https://a.test/x">Open in Purrf</a></p>{_FOOTER}'
            )
        )
        self.assertTrue(linked.startswith(f"<p>quoted: {_FOOTER}</p>"))


if __name__ == "__main__":
    unittest.main()
