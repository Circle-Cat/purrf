import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from backend.common.communication_enums import ContextType
from backend.communication.person_email_service import (
    BodyFormat,
    EmailPolicy,
    PersonAddress,
    PersonEmailService,
    recipient_options,
)
from backend.dto.email_dto import (
    EmailMessageDto,
    EmailRecipientOptionDto,
    EmailThreadDto,
)

_T0 = datetime(2026, 10, 10, 9, 0, tzinfo=timezone.utc)
_ALIAS = "mentorship-test@circlecat.org"


def _at(minutes):
    return _T0 + timedelta(minutes=minutes)


def _option(address, label="Primary contact"):
    return EmailRecipientOptionDto(address=address, label=label)


def _policy(**overrides):
    fields = {
        "user_id": 32,
        "context_type": ContextType.ACTIVITY,
        "context_id": 8,
        "sender_address": _ALIAS,
        "may_send": True,
        "body_format": BodyFormat.TEXT,
        "recipient_options": (
            _option("ann@x.com"),
            _option("ann.work@y.com", "Alternative"),
        ),
        "default_to": "ann@x.com",
    }
    fields.update(overrides)
    return EmailPolicy(**fields)


def _thread(
    thread_id=70,
    user_id=32,
    context_type=ContextType.ACTIVITY,
    context_id=8,
    subject="Your round",
):
    return SimpleNamespace(
        thread_id=thread_id,
        user_id=user_id,
        context_type=context_type,
        context_id=context_id,
        subject=subject,
        gmail_thread_id=f"g{thread_id}",
        archived_at=None,
    )


def _in(message_id, minutes, sender="Ann <ann@x.com>", attachments=None, thread_id=70):
    return SimpleNamespace(
        message_id=message_id,
        thread_id=thread_id,
        direction="inbound",
        inbound_kind="human",
        from_address=sender,
        to_addresses=_ALIAS,
        failed_recipients=None,
        gmail_internal_date=_at(minutes),
        created_at=_at(minutes + 1),
        sent_by_user_id=None,
        attachments=attachments,
        gmail_message_id=f"gm-{message_id}",
    )


def _out(message_id, minutes, to="ann@x.com", sent_by=900, thread_id=70):
    return SimpleNamespace(
        message_id=message_id,
        thread_id=thread_id,
        direction="outbound",
        inbound_kind=None,
        from_address=_ALIAS,
        to_addresses=to,
        failed_recipients=None,
        gmail_internal_date=None,
        created_at=_at(minutes),
        sent_by_user_id=sent_by,
        attachments=None,
        gmail_message_id=f"gm-{message_id}",
    )


class _Fixture(unittest.IsolatedAsyncioTestCase):
    """Repositories backed by dicts the tests fill in."""

    def setUp(self):
        self.session = Mock()
        self.threads = {}
        self.messages = {}
        self.conversation = Mock()
        self.conversation.sender_address = "recruiting@circlecat.org"
        self.conversation.list_conversation = AsyncMock(return_value=[])
        self.conversation.send = AsyncMock(side_effect=self._send)
        self.thread_repo = Mock()
        self.thread_repo.get = AsyncMock(
            side_effect=lambda s, tid: self.threads.get(tid)
        )
        self.thread_repo.list_by_person_context = AsyncMock(
            side_effect=lambda s, uid, ctype, cid: [
                t
                for t in self.threads.values()
                if (t.user_id, t.context_type, t.context_id) == (uid, ctype, cid)
            ]
        )
        self.message_repo = Mock()
        self.message_repo.list_by_thread = AsyncMock(
            side_effect=lambda s, tid: list(self.messages.get(tid, []))
        )
        self.message_repo.get = AsyncMock(
            side_effect=lambda s, mid: next(
                (m for ms in self.messages.values() for m in ms if m.message_id == mid),
                None,
            )
        )
        self.users = Mock()
        self.users.get_all_by_ids = AsyncMock(return_value=[])
        self.user_emails = Mock()
        self.user_emails.list_by_user_id = AsyncMock(return_value=[])
        self.registry = Mock()
        self.gmail = Mock()
        self.gmail.get_attachment = Mock(return_value=b"BYTES")
        self.service = PersonEmailService(
            conversation_service=self.conversation,
            thread_repository=self.thread_repo,
            message_repository=self.message_repo,
            users_repository=self.users,
            user_emails_repository=self.user_emails,
            context_registry=self.registry,
            gmail_client=self.gmail,
        )

    async def _send(self, session, **kwargs):
        return SimpleNamespace(
            message_id=999,
            thread_id=kwargs.get("thread_id") or 71,
            subject=kwargs["subject"],
            to_addresses=", ".join(kwargs["to"]),
        )


class PersonEmailAddressesTest(_Fixture):
    async def test_primary_first_then_the_others_in_the_order_added(self):
        self.user_emails.list_by_user_id.return_value = [
            SimpleNamespace(email_id=3, email="old@y.com", is_primary=False),
            SimpleNamespace(email_id=5, email="ann@x.com", is_primary=True),
            SimpleNamespace(email_id=4, email="pending@z.com", is_primary=False),
            SimpleNamespace(email_id=6, email="OLD@y.com", is_primary=False),
        ]

        addresses = await self.service.person_email_addresses(self.session, 32)

        self.assertEqual(
            addresses,
            [
                PersonAddress(address="ann@x.com", is_primary=True),
                PersonAddress(address="old@y.com", is_primary=False),
                PersonAddress(address="pending@z.com", is_primary=False),
            ],
        )
        self.user_emails.list_by_user_id.assert_awaited_once_with(self.session, 32)

    async def test_no_addresses_is_an_empty_list(self):
        self.assertEqual(await self.service.person_email_addresses(self.session, 32), [])


class RecipientOptionsTest(unittest.TestCase):
    def _labelled(self, addresses, default):
        return [(o.address, o.label) for o in recipient_options(addresses, default)]

    def test_the_default_comes_first_and_everything_else_is_alternative(self):
        self.assertEqual(
            self._labelled(["old@y.com", "ann@x.com", "OLD@y.com"], "ann@x.com"),
            [("ann@x.com", "Primary contact"), ("old@y.com", "Alternative")],
        )

    def test_the_default_is_matched_without_case_and_kept_as_given(self):
        self.assertEqual(
            self._labelled(["sofia@x.com", "sofia.old@y.com"], "Sofia@X.com"),
            [("Sofia@X.com", "Primary contact"), ("sofia.old@y.com", "Alternative")],
        )

    def test_a_default_outside_the_addresses_is_still_offered_first(self):
        self.assertEqual(
            self._labelled(["ann@x.com"], "contact@z.com"),
            [("contact@z.com", "Primary contact"), ("ann@x.com", "Alternative")],
        )

    def test_no_default_means_no_primary_contact(self):
        self.assertEqual(
            self._labelled(["ann@x.com", "old@y.com"], None),
            [("ann@x.com", "Alternative"), ("old@y.com", "Alternative")],
        )
        self.assertEqual(recipient_options([], None), [])


class ConversationTest(_Fixture):
    def _listed(self, *messages):
        return [
            EmailThreadDto(
                thread_id=70,
                created_at=_T0,
                messages=list(messages),
                reply_alias="recruiting@circlecat.org",
            )
        ]

    async def test_reads_the_policy_context_and_reports_what_the_viewer_may_do(self):
        self.conversation.list_conversation.return_value = self._listed()

        result = await self.service.conversation(self.session, _policy())

        self.conversation.list_conversation.assert_awaited_once_with(
            self.session, ContextType.ACTIVITY, 8, user_id=32
        )
        self.assertTrue(result.can_send)
        self.assertEqual(result.sender_address, _ALIAS)
        self.assertEqual(result.default_to, "ann@x.com")
        self.assertEqual(
            [o.address for o in result.recipient_options],
            ["ann@x.com", "ann.work@y.com"],
        )
        self.assertEqual(result.threads[0].reply_alias, _ALIAS)

    async def test_no_sender_address_means_nobody_can_send(self):
        result = await self.service.conversation(
            self.session, _policy(sender_address=None)
        )

        self.assertFalse(result.can_send)
        self.assertIsNone(result.sender_address)

    async def test_a_reader_without_write_cannot_send(self):
        result = await self.service.conversation(self.session, _policy(may_send=False))

        self.assertFalse(result.can_send)

    async def test_each_message_names_who_sent_it_through_purrf(self):
        ours = EmailMessageDto(
            message_id=1, direction="outbound", created_at=_T0, sent_by_user_id=900
        )
        gone = EmailMessageDto(
            message_id=2, direction="outbound", created_at=_T0, sent_by_user_id=901
        )
        theirs = EmailMessageDto(message_id=3, direction="inbound", created_at=_T0)
        self.conversation.list_conversation.return_value = self._listed(
            ours, gone, theirs
        )
        self.users.get_all_by_ids.return_value = [
            SimpleNamespace(
                user_id=900, first_name="Ada", last_name="Ng", preferred_name="Addy"
            )
        ]

        result = await self.service.conversation(self.session, _policy())

        self.assertEqual(
            [m.sent_by_name for m in result.threads[0].messages], ["Addy", None, None]
        )
        self.users.get_all_by_ids.assert_awaited_once_with(self.session, [900, 901])

    async def test_nobody_sent_through_purrf_looks_nobody_up(self):
        self.conversation.list_conversation.return_value = self._listed(
            EmailMessageDto(message_id=3, direction="inbound", created_at=_T0)
        )

        await self.service.conversation(self.session, _policy())

        self.users.get_all_by_ids.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
