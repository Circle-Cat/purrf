import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from backend.common.communication_enums import ContextType
from backend.common.exceptions import NotFoundError
from backend.common.permissions import Permission
from backend.communication.inbox_aliases import InboxAliases
from backend.communication.person_email_service import BodyFormat, PersonAddress
from backend.dto.email_dto import EmailConversationDto
from backend.dto.user_context_dto import UserContextDto
from backend.mentorship.participant_email_service import (
    MentorshipParticipantEmailPolicy,
    ParticipantEmailService,
)

_ALIAS = "mentorship-test@circlecat.org"


def _viewer(*permissions):
    return UserContextDto(
        sub="v",
        primary_email="v@circlecat.org",
        user_id=900,
        permissions=frozenset(permissions),
    )


class _Fixture(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.session = Mock()
        self.session.commit = AsyncMock()
        self.rounds = Mock()
        self.rounds.get_by_round_id = AsyncMock(return_value=SimpleNamespace(round_id=8))
        self.users = Mock()
        self.users.get_user_by_user_id = AsyncMock(
            return_value=SimpleNamespace(user_id=32)
        )
        self.person_email = Mock()
        self.person_email.person_email_addresses = AsyncMock(
            return_value=[
                PersonAddress(address="ann@x.com", is_primary=True),
                PersonAddress(address="ann.work@y.com", is_primary=False),
            ]
        )
        self.conversation = EmailConversationDto(threads=[])
        self.person_email.conversation = AsyncMock(return_value=self.conversation)
        self.person_email.send_new = AsyncMock()
        self.person_email.reply = AsyncMock()
        self.person_email.refresh = AsyncMock(return_value=2)
        self.person_email.read_attachment = AsyncMock(return_value=(b"BYTES", "cv.pdf"))
        self.policy = MentorshipParticipantEmailPolicy(
            rounds_repository=self.rounds,
            users_repository=self.users,
            person_email_service=self.person_email,
            aliases=InboxAliases(mentorship=_ALIAS),
        )
        self.service = ParticipantEmailService(
            policy=self.policy, person_email_service=self.person_email
        )


class PolicyTest(_Fixture):
    async def test_a_writer_may_send_from_the_mentorship_alias_to_the_person(self):
        policy = await self.policy.resolve(
            self.session, 8, 32, _viewer(Permission.MENTORSHIP_ADMIN_WRITE)
        )

        self.assertEqual(
            (policy.user_id, policy.context_type, policy.context_id),
            (32, ContextType.ACTIVITY, 8),
        )
        self.assertEqual(policy.sender_address, _ALIAS)
        self.assertTrue(policy.can_send)
        self.assertEqual(policy.body_format, BodyFormat.TEXT)
        self.assertEqual(policy.default_to, "ann@x.com")
        self.assertEqual(
            [(o.address, o.label) for o in policy.recipient_options],
            [("ann@x.com", "Primary contact"), ("ann.work@y.com", "Alternative")],
        )

    async def test_a_reader_sees_but_cannot_send(self):
        policy = await self.policy.resolve(
            self.session, 8, 32, _viewer(Permission.MENTORSHIP_ADMIN_READ)
        )

        self.assertFalse(policy.can_send)

    async def test_no_mentorship_alias_means_nobody_can_send(self):
        policy = await MentorshipParticipantEmailPolicy(
            rounds_repository=self.rounds,
            users_repository=self.users,
            person_email_service=self.person_email,
            aliases=InboxAliases(),
        ).resolve(self.session, 8, 32, _viewer(Permission.MENTORSHIP_ADMIN_WRITE))

        self.assertIsNone(policy.sender_address)
        self.assertFalse(policy.can_send)

    async def test_without_a_primary_address_nothing_is_preselected(self):
        self.person_email.person_email_addresses.return_value = [
            PersonAddress(address="old@y.com", is_primary=False)
        ]

        policy = await self.policy.resolve(
            self.session, 8, 32, _viewer(Permission.MENTORSHIP_ADMIN_WRITE)
        )

        self.assertIsNone(policy.default_to)
        self.assertEqual(
            [(o.address, o.label) for o in policy.recipient_options],
            [("old@y.com", "Alternative")],
        )

    async def test_an_unknown_round_or_person_is_not_found(self):
        self.rounds.get_by_round_id.return_value = None
        with self.assertRaises(NotFoundError):
            await self.policy.resolve(self.session, 8, 32, _viewer())

        self.rounds.get_by_round_id.return_value = SimpleNamespace(round_id=8)
        self.users.get_user_by_user_id.return_value = None
        with self.assertRaises(NotFoundError):
            await self.policy.resolve(self.session, 8, 32, _viewer())

        self.person_email.person_email_addresses.assert_not_awaited()


class ServiceTest(_Fixture):
    def _writer(self):
        return _viewer(Permission.MENTORSHIP_ADMIN_WRITE)

    async def test_send_writes_commits_then_reads_back(self):
        calls = []
        self.person_email.send_new.side_effect = lambda *a, **k: calls.append("send")
        self.session.commit.side_effect = lambda: calls.append("commit")
        self.person_email.conversation.side_effect = (
            lambda *a: calls.append("read") or self.conversation
        )

        result = await self.service.send_email(
            self.session, 8, 32, self._writer(), to=["ann@x.com"], subject="Hi", body="Hello"
        )

        self.assertIs(result, self.conversation)
        self.assertEqual(calls, ["send", "commit", "read"])
        policy = self.person_email.send_new.call_args.args[1]
        self.assertEqual((policy.user_id, policy.context_id), (32, 8))
        self.assertEqual(
            self.person_email.send_new.call_args.kwargs,
            {"sender_user_id": 900, "to": ["ann@x.com"], "subject": "Hi", "body": "Hello"},
        )

    async def test_reply_passes_the_thread_and_what_was_seen(self):
        await self.service.reply(
            self.session,
            8,
            32,
            self._writer(),
            thread_id=70,
            body="Thanks",
            last_seen_message_id=12,
        )

        self.assertEqual(
            self.person_email.reply.call_args.kwargs,
            {
                "sender_user_id": 900,
                "thread_id": 70,
                "body": "Thanks",
                "last_seen_message_id": 12,
            },
        )
        self.session.commit.assert_awaited_once()

    async def test_refresh_reports_new_replies_with_the_conversation(self):
        result = await self.service.refresh(self.session, 8, 32, self._writer())

        self.assertEqual(result.new_replies, 2)
        self.assertEqual(result.conversation, self.conversation)
        self.session.commit.assert_awaited_once()

    async def test_reading_does_not_commit(self):
        result = await self.service.get_emails(
            self.session, 8, 32, _viewer(Permission.MENTORSHIP_ADMIN_READ)
        )

        self.assertIs(result, self.conversation)
        self.session.commit.assert_not_awaited()

    async def test_attachment_is_read_within_the_person_and_round(self):
        content = await self.service.attachment(
            self.session,
            8,
            32,
            _viewer(Permission.MENTORSHIP_ADMIN_READ),
            message_id=5,
            index=0,
        )

        self.assertEqual(content, (b"BYTES", "cv.pdf"))
        policy, message_id, index = self.person_email.read_attachment.call_args.args[1:]
        self.assertEqual(
            (policy.context_type, policy.context_id, message_id, index),
            (ContextType.ACTIVITY, 8, 5, 0),
        )

    async def test_an_unknown_round_writes_nothing(self):
        self.rounds.get_by_round_id.return_value = None

        with self.assertRaises(NotFoundError):
            await self.service.send_email(
                self.session, 8, 32, self._writer(), to=["ann@x.com"], subject="Hi", body="Hello"
            )

        self.person_email.send_new.assert_not_awaited()
        self.session.commit.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
