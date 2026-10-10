import unittest
from datetime import datetime, timedelta, timezone
from itertools import count
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from backend.common.communication_enums import ContextType, EmailDirection, InboundKind
from backend.common.inbox_enums import INBOX_SUBJECT_TYPE
from backend.common.mentorship_enums import MentorshipEvent
from backend.mentorship.participant_email_notifier import ParticipantEmailNotifier

_T0 = datetime(2026, 10, 1, 9, 0, tzinfo=timezone.utc)
_ids = count(1)


def _at(minutes):
    return _T0 + timedelta(minutes=minutes)


def _in(minutes, kind=InboundKind.HUMAN, sender="ann@x.com", failed=None):
    return SimpleNamespace(
        message_id=next(_ids),
        direction=EmailDirection.INBOUND,
        inbound_kind=kind,
        from_address=sender,
        to_addresses=None,
        subject="Re: Your round",
        gmail_internal_date=_at(minutes),
        created_at=_at(minutes + 1),
        failed_recipients=failed,
        sent_by_user_id=None,
    )


def _out(minutes, sent_by=None, subject="Your round"):
    return SimpleNamespace(
        message_id=next(_ids),
        direction=EmailDirection.OUTBOUND,
        inbound_kind=None,
        from_address="mentorship-test@circlecat.org",
        to_addresses="ann@x.com",
        subject=subject,
        gmail_internal_date=None,
        created_at=_at(minutes),
        failed_recipients=None,
        sent_by_user_id=sent_by,
    )


class ParticipantEmailNotifierTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.messages = Mock()
        self.users = Mock()
        self.users.get_user_by_user_id = AsyncMock(
            return_value=SimpleNamespace(
                first_name="Ann", last_name="Lee", preferred_name=None
            )
        )
        self.notifier = ParticipantEmailNotifier(
            message_repository=self.messages, users_repository=self.users
        )
        self.session = Mock()
        self.thread = SimpleNamespace(
            thread_id=70,
            user_id=32,
            context_type=ContextType.ACTIVITY,
            context_id=8,
            subject="Your round",
            archived_at=None,
        )
        patcher = patch(
            "backend.mentorship.participant_email_notifier.record_event",
            new_callable=AsyncMock,
        )
        self.record = patcher.start()
        self.addCleanup(patcher.stop)

    async def _after_sync(self, existing, new):
        self.messages.list_by_thread = AsyncMock(return_value=existing + new)
        return await self.notifier.after_sync(self.session, self.thread, new)

    async def test_a_reply_that_needs_an_answer_records_email_received_once(self):
        recorded = await self._after_sync(
            [_out(0, sent_by=900)], [_in(5, sender="Ann <ann@x.com>")]
        )

        self.assertTrue(recorded)
        self.record.assert_awaited_once_with(
            self.session,
            subject_type=INBOX_SUBJECT_TYPE,
            subject_id=70,
            actor_id=None,
            event_type=MentorshipEvent.EMAIL_RECEIVED,
            details={
                "roundId": 8,
                "userId": 32,
                "personName": "Ann Lee",
                "threadId": 70,
                "subject": "Your round",
                "from": "Ann <ann@x.com>",
            },
        )
        self.users.get_user_by_user_id.assert_awaited_once_with(self.session, 32)

    async def test_more_mail_on_a_waiting_thread_records_nothing(self):
        recorded = await self._after_sync([_in(0)], [_in(5)])

        self.assertFalse(recorded)
        self.record.assert_not_awaited()

    async def test_a_bounce_records_email_bounced_even_without_a_known_sender(self):
        await self._after_sync(
            [_out(0, sent_by=None, subject="Dates")],
            [
                _in(
                    5,
                    kind=InboundKind.BOUNCE,
                    sender="mailer@x.com",
                    failed="ann@x.com",
                )
            ],
        )

        self.record.assert_awaited_once_with(
            self.session,
            subject_type=INBOX_SUBJECT_TYPE,
            subject_id=70,
            actor_id=None,
            event_type=MentorshipEvent.EMAIL_BOUNCED,
            details={
                "roundId": 8,
                "userId": 32,
                "personName": "Ann Lee",
                "threadId": 70,
                "subject": "Dates",
                "bouncedTo": "ann@x.com",
            },
        )

    async def test_nothing_new_reads_nothing(self):
        self.assertFalse(await self.notifier.after_sync(self.session, self.thread, []))

        self.users.get_user_by_user_id.assert_not_called()
        self.record.assert_not_awaited()

    async def test_auto_replies_alone_record_nothing_and_look_nobody_up(self):
        await self._after_sync(
            [_out(0, sent_by=900)], [_in(5, kind=InboundKind.AUTO_REPLY)]
        )

        self.record.assert_not_awaited()
        self.users.get_user_by_user_id.assert_not_awaited()

    async def test_threads_without_a_person_or_round_or_not_activity_record_nothing(
        self,
    ):
        base = self.thread
        for change in (
            {"user_id": None},
            {"context_id": None},
            {"context_type": ContextType.APPLICATION},
        ):
            with self.subTest(change=change):
                self.thread = SimpleNamespace(**{**vars(base), **change})
                recorded = await self._after_sync([_out(0, sent_by=900)], [_in(5)])

                self.assertFalse(recorded)
                self.record.assert_not_awaited()
                self.users.get_user_by_user_id.assert_not_called()

    async def test_a_missing_user_row_gives_an_empty_person_name(self):
        self.users.get_user_by_user_id = AsyncMock(return_value=None)

        await self._after_sync([_out(0, sent_by=900)], [_in(5)])

        self.assertEqual("", self.record.await_args.kwargs["details"]["personName"])

    async def test_a_preferred_name_is_the_person_name(self):
        self.users.get_user_by_user_id = AsyncMock(
            return_value=SimpleNamespace(
                first_name="Ann", last_name="Lee", preferred_name="Annie"
            )
        )

        await self._after_sync([_out(0, sent_by=900)], [_in(5)])

        self.assertEqual(
            "Annie", self.record.await_args.kwargs["details"]["personName"]
        )


if __name__ == "__main__":
    unittest.main()
