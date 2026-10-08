import unittest
from unittest.mock import AsyncMock, Mock, patch

from backend.common.communication_enums import InboxService
from backend.common.inbox_enums import INBOX_SUBJECT_TYPE, InboxEvent
from backend.communication import recipient_resolvers  # noqa: F401 (registers)
from backend.notification_management import recipient_registry
from backend.repository.user_permissions_repository import UserPermissionsRepository


def _event(event_type, details):
    return Mock(event_type=event_type, subject_type=INBOX_SUBJECT_TYPE, details=details)


class NeedsReplyRecipientsTest(unittest.IsolatedAsyncioTestCase):
    async def _resolve(self, service):
        session = Mock()
        with patch.object(
            UserPermissionsRepository,
            "get_active_users_with_permission",
            new_callable=AsyncMock,
            return_value=[Mock(user_id=11), Mock(user_id=12)],
        ) as lookup:
            recipients = await recipient_registry.resolve_recipients(
                session, _event(InboxEvent.NEEDS_REPLY, {"service": service})
            )
        return recipients, lookup, session

    async def test_each_service_reaches_the_holders_of_its_permission(self):
        expected = {
            InboxService.MENTORSHIP: "mentorship.admin.write",
            InboxService.RECRUITING: "recruiting.application.advance",
            InboxService.INQUIRIES: "inquiries.manage",
        }
        for service, permission in expected.items():
            with self.subTest(service=service):
                recipients, lookup, session = await self._resolve(service)

                self.assertEqual(recipients, {11, 12})
                lookup.assert_awaited_once_with(session, permission)

    async def test_an_unknown_service_is_a_write_site_bug(self):
        with self.assertRaises(ValueError):
            await self._resolve("broadcast")


class BouncedRecipientsTest(unittest.IsolatedAsyncioTestCase):
    async def test_the_sender_of_the_bounced_mail_hears_about_it(self):
        recipients = await recipient_registry.resolve_recipients(
            Mock(), _event(InboxEvent.BOUNCED, {"senderUserId": 9})
        )

        self.assertEqual(recipients, {9})

    async def test_no_sender_means_nobody(self):
        recipients = await recipient_registry.resolve_recipients(
            Mock(), _event(InboxEvent.BOUNCED, {"senderUserId": None})
        )

        self.assertEqual(recipients, set())


class SilentEventsTest(unittest.IsolatedAsyncioTestCase):
    async def test_the_trail_only_events_reach_nobody(self):
        for event_type in (
            InboxEvent.ASSIGNED,
            InboxEvent.UNASSIGNED,
            InboxEvent.ARCHIVED,
            InboxEvent.UNARCHIVED,
            InboxEvent.MOVED,
        ):
            with self.subTest(event_type=event_type):
                self.assertNotIn(event_type, recipient_registry._RESOLVERS)


if __name__ == "__main__":
    unittest.main()
