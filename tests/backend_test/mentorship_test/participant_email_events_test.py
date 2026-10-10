import unittest
from unittest.mock import AsyncMock, Mock, patch

from backend.common.inbox_enums import INBOX_SUBJECT_TYPE
from backend.common.mentorship_enums import MentorshipEvent
from backend.entity.event_entity import EventEntity
from backend.mentorship import notification_renderers  # noqa: F401 (registers)
from backend.mentorship import recipient_resolvers  # noqa: F401 (registers)
from backend.notification_management import recipient_registry, render_registry
from backend.repository.email_message_repository import EmailMessageRepository
from backend.repository.user_permissions_repository import UserPermissionsRepository

_DETAILS = {
    "roundId": 8,
    "userId": 32,
    "personName": "Ann <Lee>",
    "threadId": 70,
    "subject": "Your round & dates",
}


def _event(event_type, **details):
    return EventEntity(
        subject_type=INBOX_SUBJECT_TYPE,
        subject_id=70,
        actor_id=None,
        event_type=event_type,
        details={**_DETAILS, **details},
    )


def _received(**details):
    return _event(MentorshipEvent.EMAIL_RECEIVED, **{"from": "ann@x.com", **details})


def _bounced(**details):
    return _event(
        MentorshipEvent.EMAIL_BOUNCED, **{"bouncedTo": "ann@x.com", **details}
    )


class _Patched(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        senders = patch.object(
            EmailMessageRepository,
            "list_sender_ids_by_thread",
            new_callable=AsyncMock,
            return_value=set(),
        )
        holders = patch.object(
            UserPermissionsRepository,
            "get_active_users_with_permission",
            new_callable=AsyncMock,
            return_value=[Mock(user_id=11), Mock(user_id=12)],
        )
        self.senders = senders.start()
        self.addCleanup(senders.stop)
        self.holders = holders.start()
        self.addCleanup(holders.stop)
        self.session = Mock()


class ReceivedRecipientsTest(_Patched):
    async def test_whoever_wrote_into_the_thread_through_purrf(self):
        self.senders.return_value = {900, 901}

        recipients = await recipient_registry.resolve_recipients(
            self.session, _received()
        )

        self.assertEqual(recipients, {900, 901})
        self.senders.assert_awaited_once_with(self.session, 70)
        self.holders.assert_not_awaited()

    async def test_nobody_wrote_through_purrf_so_every_mentorship_writer(self):
        recipients = await recipient_registry.resolve_recipients(
            self.session, _received()
        )

        self.assertEqual(recipients, {11, 12})
        self.holders.assert_awaited_once_with(self.session, "mentorship.admin.write")


class BouncedRecipientsTest(_Patched):
    async def test_only_the_senders_never_the_writers(self):
        self.assertEqual(
            await recipient_registry.resolve_recipients(self.session, _bounced()),
            set(),
        )
        self.senders.return_value = {900}
        self.assertEqual(
            await recipient_registry.resolve_recipients(self.session, _bounced()),
            {900},
        )
        self.holders.assert_not_awaited()


class RenderTest(unittest.IsolatedAsyncioTestCase):
    async def test_a_reply_names_the_person_and_where_to_answer(self):
        subject, body = await render_registry.render(Mock(), _received())

        self.assertEqual(subject, "New email reply from a mentorship participant")
        self.assertIn(
            "Ann &lt;Lee&gt; replied to “Your round &amp; dates” (ann@x.com).", body
        )
        self.assertIn("Mentorship Management", body)
        self.assertIn("Participants", body)
        self.assertNotIn("<Lee>", body)

    async def test_a_bounce_names_the_address_that_failed(self):
        subject, body = await render_registry.render(Mock(), _bounced())

        self.assertEqual(
            subject, "Your email to a mentorship participant was not delivered"
        )
        self.assertIn(
            "Your email to Ann &lt;Lee&gt; (ann@x.com) about “Your round &amp; dates”"
            " was not delivered.",
            body,
        )

    async def test_a_missing_name_still_reads(self):
        _, body = await render_registry.render(Mock(), _received(personName=""))

        self.assertIn("A participant replied", body)


if __name__ == "__main__":
    unittest.main()
