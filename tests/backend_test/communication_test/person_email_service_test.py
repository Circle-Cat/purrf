import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from backend.common.communication_enums import ContextType
from backend.common.exceptions import ConflictError, NotFoundError
from backend.communication.person_email_service import (
    BodyFormat,
    EmailPolicy,
    PersonAddress,
    PersonEmailService,
    choose_default,
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


def _row(email_id, email, is_primary=False, otp_confirmed=True):
    return SimpleNamespace(
        email_id=email_id,
        email=email,
        is_primary=is_primary,
        otp_confirmed=otp_confirmed,
    )


class PersonEmailAddressesTest(_Fixture):
    async def test_only_verified_addresses_primary_first_then_in_the_order_added(self):
        self.user_emails.list_by_user_id.return_value = [
            _row(3, "old@y.com"),
            _row(5, "ann@x.com", is_primary=True),
            _row(4, "pending@z.com", otp_confirmed=False),
            _row(6, "OLD@y.com"),
            _row(7, "ANN@x.com", otp_confirmed=False),
            _row(8, "  ", otp_confirmed=True),
        ]

        addresses = await self.service.person_email_addresses(self.session, 32)

        self.assertEqual(
            addresses,
            [
                PersonAddress(address="ann@x.com", is_primary=True),
                PersonAddress(address="old@y.com", is_primary=False),
            ],
        )
        self.user_emails.list_by_user_id.assert_awaited_once_with(self.session, 32)

    async def test_an_unverified_primary_is_not_offered(self):
        self.user_emails.list_by_user_id.return_value = [
            _row(1, "ann@x.com", is_primary=True, otp_confirmed=False),
            _row(2, "work@y.com"),
        ]

        addresses = await self.service.person_email_addresses(self.session, 32)

        self.assertEqual(addresses, [PersonAddress("work@y.com", False)])

    async def test_a_person_with_only_unverified_addresses_gets_none(self):
        self.user_emails.list_by_user_id.return_value = [
            _row(1, "ann@x.com", is_primary=True, otp_confirmed=False),
            _row(2, "work@y.com", otp_confirmed=False),
        ]

        self.assertEqual(
            await self.service.person_email_addresses(self.session, 32), []
        )

    async def test_no_addresses_is_an_empty_list(self):
        self.assertEqual(
            await self.service.person_email_addresses(self.session, 32), []
        )


class ChooseDefaultTest(unittest.TestCase):
    _ADDRESSES = [
        PersonAddress("ann@x.com", True),
        PersonAddress("Old@y.com", False),
    ]

    def test_the_preferred_address_wins_in_the_stored_spelling(self):
        self.assertEqual(choose_default(self._ADDRESSES, "old@Y.com"), "Old@y.com")

    def test_a_preferred_address_that_is_not_offered_falls_back_to_the_first(self):
        self.assertEqual(choose_default(self._ADDRESSES, "gone@z.com"), "ann@x.com")

    def test_no_preferred_address_falls_back_to_the_first(self):
        self.assertEqual(choose_default(self._ADDRESSES, None), "ann@x.com")

    def test_no_addresses_means_no_default(self):
        self.assertIsNone(choose_default([], "ann@x.com"))
        self.assertIsNone(choose_default([], None))


class RecipientOptionsTest(unittest.TestCase):
    def _labelled(self, addresses, default):
        return [(o.address, o.label) for o in recipient_options(addresses, default)]

    def test_the_default_comes_first_and_everything_else_is_alternative(self):
        self.assertEqual(
            self._labelled(["old@y.com", "ann@x.com", "OLD@y.com"], "ann@x.com"),
            [("ann@x.com", "Primary contact"), ("old@y.com", "Alternative")],
        )

    def test_the_default_is_matched_without_case_and_kept_as_listed(self):
        self.assertEqual(
            self._labelled(["sofia@x.com", "sofia.old@y.com"], "Sofia@X.com"),
            [("sofia@x.com", "Primary contact"), ("sofia.old@y.com", "Alternative")],
        )

    def test_a_default_outside_the_addresses_is_never_offered(self):
        self.assertEqual(
            self._labelled(["ann@x.com"], "contact@z.com"),
            [("ann@x.com", "Alternative")],
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


class SendNewTest(_Fixture):
    async def _send_new(self, policy=None, **overrides):
        args = {
            "sender_user_id": 900,
            "to": ["ann@x.com"],
            "subject": "Your round",
            "body": "Hi Ann,\n<b>see</b> you",
        }
        args.update(overrides)
        return await self.service.send_new(self.session, policy or _policy(), **args)

    async def test_text_is_escaped_for_gmail_and_kept_as_typed(self):
        message = await self._send_new()

        kwargs = self.conversation.send.call_args.kwargs
        self.assertEqual(
            kwargs["body"],
            '<div style="white-space:pre-wrap">Hi Ann,<br>&lt;b&gt;see&lt;/b&gt; you</div>',
        )
        self.assertEqual(kwargs["body_text"], "Hi Ann,\n<b>see</b> you")
        self.assertEqual(
            (kwargs["user_id"], kwargs["context_type"], kwargs["context_id"]),
            (32, ContextType.ACTIVITY, 8),
        )
        self.assertEqual(kwargs["sender_address"], _ALIAS)
        self.assertEqual(kwargs["sender_user_id"], 900)
        self.assertNotIn("thread_id", kwargs)
        self.assertEqual(message.message_id, 999)
        self.session.commit.assert_not_called()

    async def test_rich_html_goes_out_as_written_with_no_text_copy(self):
        await self._send_new(_policy(body_format=BodyFormat.RICH), body="<p>Hi</p>")

        kwargs = self.conversation.send.call_args.kwargs
        self.assertEqual((kwargs["body"], kwargs["body_text"]), ("<p>Hi</p>", None))

    async def test_recipients_match_case_and_spacing_and_are_sent_as_offered(self):
        await self._send_new(to=[" ANN@X.com ", "ann.work@y.com", "ann@x.com"])

        self.assertEqual(
            self.conversation.send.call_args.kwargs["to"],
            ["ann@x.com", "ann.work@y.com"],
        )

    async def test_an_address_that_is_not_offered_is_refused(self):
        for to in (["ann@x.com", "eve@evil.com"], [], ["Ann <ann@x.com>"]):
            with self.subTest(to=to):
                with self.assertRaises(ValueError):
                    await self._send_new(to=to)

        self.conversation.send.assert_not_awaited()

    async def test_the_subject_is_one_line_and_fits_a_reply_prefix(self):
        await self._send_new(subject="  Your\r\nround \tdates ")
        self.assertEqual(
            self.conversation.send.call_args.kwargs["subject"], "Your round dates"
        )

        for subject in ("", " \n ", "x" * 991):
            with self.subTest(length=len(subject)):
                with self.assertRaises(ValueError):
                    await self._send_new(subject=subject)

        await self._send_new(subject="x" * 990)
        self.assertEqual(len(self.conversation.send.call_args.kwargs["subject"]), 990)

    async def test_text_body_must_say_something_and_not_too_much(self):
        for body in ("", "  \n ", "x" * 10_001):
            with self.subTest(length=len(body)):
                with self.assertRaises(ValueError):
                    await self._send_new(body=body)

        self.conversation.send.assert_not_awaited()
        await self._send_new(body="x" * 10_000)

    async def test_no_sender_address_or_no_write_refuses_before_gmail(self):
        for policy in (_policy(sender_address=None), _policy(may_send=False)):
            with self.subTest(policy=policy):
                with self.assertRaises(ValueError):
                    await self._send_new(policy)

        self.conversation.send.assert_not_awaited()


class ReplyTest(_Fixture):
    def setUp(self):
        super().setUp()
        self.threads = {
            70: _thread(70),
            71: _thread(71, user_id=33),
            72: _thread(72, context_id=9),
            73: _thread(73, context_type=ContextType.APPLICATION),
        }
        self.messages = {
            70: [_out(1, 0), _in(2, 5, sender="Ann <Ann@X.com>")],
            71: [_in(3, 0, thread_id=71)],
            72: [_in(4, 0, thread_id=72)],
            73: [_in(5, 0, thread_id=73)],
        }

    async def _reply(self, policy=None, thread_id=70, last_seen=2, body="Thanks!\nBo"):
        return await self.service.reply(
            self.session,
            policy or _policy(),
            sender_user_id=900,
            thread_id=thread_id,
            body=body,
            last_seen_message_id=last_seen,
        )

    async def test_reply_goes_to_the_newest_human_sender_in_the_same_thread(self):
        await self._reply()

        kwargs = self.conversation.send.call_args.kwargs
        self.assertEqual(kwargs["to"], ["ann@x.com"])
        self.assertEqual(kwargs["subject"], "Re: Your round")
        self.assertEqual(kwargs["thread_id"], 70)
        self.assertEqual(
            kwargs["body"],
            '<div style="white-space:pre-wrap">Thanks!<br>Bo</div>',
        )
        self.assertEqual(kwargs["body_text"], "Thanks!\nBo")
        self.assertEqual(kwargs["sender_address"], _ALIAS)
        self.assertEqual(
            (kwargs["user_id"], kwargs["context_type"], kwargs["context_id"]),
            (32, ContextType.ACTIVITY, 8),
        )

    async def test_a_newer_message_than_the_one_seen_is_a_conflict(self):
        with self.assertRaises(ConflictError) as caught:
            await self._reply(last_seen=1)

        self.assertEqual(caught.exception.code, "THREAD_CHANGED")
        self.conversation.send.assert_not_awaited()

    async def test_a_thread_of_another_person_round_or_context_is_not_found(self):
        for thread_id in (71, 72, 73, 404):
            with self.subTest(thread_id=thread_id):
                with self.assertRaises(NotFoundError):
                    await self._reply(thread_id=thread_id, last_seen=None)

        self.conversation.send.assert_not_awaited()

    async def test_no_sender_address_is_refused(self):
        with self.assertRaises(ValueError):
            await self._reply(_policy(sender_address=None))

        self.conversation.send.assert_not_awaited()

    async def test_an_empty_reply_is_refused(self):
        with self.assertRaises(ValueError):
            await self._reply(body="  ")

        self.conversation.send.assert_not_awaited()


class ReplyIntoTest(_Fixture):
    """The core the Inbox shares: no policy, the caller names the sender."""

    async def test_a_thread_nobody_wrote_in_has_nobody_to_reply_to(self):
        self.messages = {70: []}

        with self.assertRaises(ValueError):
            await self.service.reply_into(
                self.session,
                _thread(70),
                body="<p>x</p>",
                body_format=BodyFormat.RICH,
                last_seen_message_id=None,
                sender_address=_ALIAS,
                sender_user_id=900,
            )

        self.conversation.send.assert_not_awaited()

    async def test_rich_reply_keeps_the_html(self):
        self.messages = {70: [_in(2, 5)]}

        await self.service.reply_into(
            self.session,
            _thread(70),
            body="<p>x</p>",
            body_format=BodyFormat.RICH,
            last_seen_message_id=2,
            sender_address=_ALIAS,
            sender_user_id=900,
        )

        kwargs = self.conversation.send.call_args.kwargs
        self.assertEqual((kwargs["body"], kwargs["body_text"]), ("<p>x</p>", None))


class RefreshTest(_Fixture):
    def setUp(self):
        super().setUp()
        self.threads = {70: _thread(70), 74: _thread(74), 71: _thread(71, user_id=33)}
        self.messages = {70: [_out(1, 0)], 74: [_in(2, 0, thread_id=74)], 71: []}
        self.handler = Mock()
        self.handler.sync_tracked_thread = AsyncMock(side_effect=self._sync)
        self.registry.get = Mock(return_value=self.handler)

    async def _sync(self, session, thread):
        if thread.thread_id == 70:
            self.messages[70] += [
                _in(10, 5),
                _out(11, 6),
                _in(12, 7, sender="mailer-daemon@x.com"),
            ]
        return 0

    async def test_each_thread_of_the_person_syncs_through_its_domain_handler(self):
        new_inbound = await self.service.refresh(self.session, _policy())

        self.assertEqual(new_inbound, 2)
        self.assertEqual(
            [
                c.args[1].thread_id
                for c in self.handler.sync_tracked_thread.await_args_list
            ],
            [70, 74],
        )
        self.registry.get.assert_called_with(ContextType.ACTIVITY)
        self.session.commit.assert_not_called()

    async def test_nothing_new_is_zero(self):
        self.handler.sync_tracked_thread = AsyncMock(return_value=0)

        self.assertEqual(await self.service.refresh(self.session, _policy()), 0)

    async def test_a_context_with_no_handler_is_refused(self):
        self.registry.get = Mock(return_value=None)

        with self.assertRaises(ValueError):
            await self.service.refresh(self.session, _policy())


class AttachmentTest(_Fixture):
    def setUp(self):
        super().setUp()
        self.threads = {70: _thread(70), 71: _thread(71, user_id=33)}
        self.messages = {
            70: [
                _in(
                    2,
                    0,
                    attachments=[
                        {"name": "cv.pdf", "size": 3, "gmailAttachmentId": "att-a"},
                        {"attachment_id": "a1", "filename": "old.pdf"},
                    ],
                )
            ],
            71: [
                _in(
                    3,
                    0,
                    attachments=[
                        {"name": "x.pdf", "size": 1, "gmailAttachmentId": "att-x"}
                    ],
                    thread_id=71,
                )
            ],
        }

    async def test_downloads_by_position_from_gmail(self):
        content, name = await self.service.read_attachment(
            self.session, _policy(), 2, 0
        )

        self.assertEqual((content, name), (b"BYTES", "cv.pdf"))
        self.gmail.get_attachment.assert_called_once_with("gm-2", "att-a")

    async def test_a_message_of_another_person_is_not_found(self):
        for message_id in (3, 404):
            with self.subTest(message_id=message_id):
                with self.assertRaises(NotFoundError):
                    await self.service.read_attachment(
                        self.session, _policy(), message_id, 0
                    )

        self.gmail.get_attachment.assert_not_called()

    async def test_a_bad_index_or_a_legacy_entry_is_refused_without_calling_gmail(self):
        for index in (-1, 2, 1):
            with self.subTest(index=index):
                with self.assertRaisesRegex(ValueError, "attachment not found"):
                    await self.service.read_attachment(
                        self.session, _policy(), 2, index
                    )

        self.gmail.get_attachment.assert_not_called()


if __name__ == "__main__":
    unittest.main()
