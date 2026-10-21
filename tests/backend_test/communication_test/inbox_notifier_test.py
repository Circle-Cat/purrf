import unittest
from datetime import datetime, timedelta, timezone
from itertools import count
from unittest.mock import AsyncMock, Mock, patch

from backend.common.communication_enums import (
    ContextType,
    EmailDirection,
    InboundKind,
    InboxService,
)
from backend.common.inbox_enums import INBOX_SUBJECT_TYPE, InboxEvent
from backend.communication.inbox_notifier import InboxNotifier

_T0 = datetime(2026, 10, 1, 9, 0, tzinfo=timezone.utc)
_ids = count(1)


def _at(minutes):
    return _T0 + timedelta(minutes=minutes)


def _inbound(
    minutes, kind=InboundKind.HUMAN, sender="asker@ext.com", failed=None, stored=None
):
    # created_at is when Purrf stored it, shortly after Gmail received it.
    return Mock(
        message_id=next(_ids),
        direction=EmailDirection.INBOUND,
        inbound_kind=kind,
        from_address=sender,
        subject="Re: A question",
        gmail_internal_date=_at(minutes),
        created_at=_at(stored if stored is not None else minutes + 1),
        failed_recipients=failed,
        sent_by_user_id=None,
    )


def _outbound(minutes, sent_by=None, subject="Our answer"):
    # Our own mail has no Gmail internal date; created_at is its send time.
    return Mock(
        message_id=next(_ids),
        direction=EmailDirection.OUTBOUND,
        inbound_kind=None,
        from_address="mentorship@purrf.example",
        to_addresses="asker@ext.com",
        subject=subject,
        gmail_internal_date=None,
        created_at=_at(minutes),
        failed_recipients=None,
        sent_by_user_id=sent_by,
    )


def _bounce(minutes, failed="asker@ext.com"):
    return _inbound(
        minutes, kind=InboundKind.BOUNCE, sender="mailer-daemon@x.com", failed=failed
    )


class InboxNotifierTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.messages = AsyncMock()
        self.services = AsyncMock()
        self.services.service_of.return_value = InboxService.MENTORSHIP
        self.notifier = InboxNotifier(
            message_repository=self.messages, thread_service_resolver=self.services
        )
        self.session = Mock()
        self.thread = Mock(
            thread_id=77,
            subject="A question",
            context_type=ContextType.MENTORSHIP_INBOX,
            archived_at=None,
        )
        patcher = patch(
            "backend.communication.inbox_notifier.record_event", new_callable=AsyncMock
        )
        self.record = patcher.start()
        self.addCleanup(patcher.stop)

    async def _after_sync(self, existing, new):
        self.messages.list_by_thread.return_value = existing + new
        return await self.notifier.after_sync(self.session, self.thread, new)

    def _events(self, event_type):
        return [
            c.kwargs
            for c in self.record.await_args_list
            if c.kwargs["event_type"] == event_type
        ]

    async def test_the_first_human_inbound_records_needs_reply_once(self):
        first = _inbound(0)

        recorded = await self._after_sync([], [first])

        self.assertTrue(recorded)
        self.record.assert_awaited_once_with(
            self.session,
            subject_type=INBOX_SUBJECT_TYPE,
            subject_id=77,
            actor_id=None,
            event_type=InboxEvent.NEEDS_REPLY,
            details={
                "service": InboxService.MENTORSHIP,
                "subject": "A question",
                "from": "asker@ext.com",
            },
        )
        self.messages.list_by_thread.assert_awaited_once_with(self.session, 77)

    async def test_a_second_unanswered_inbound_does_not_record_again(self):
        recorded = await self._after_sync([_inbound(0)], [_inbound(5)])

        self.assertFalse(recorded)
        self.record.assert_not_awaited()

    async def test_an_inbound_after_our_reply_records_again(self):
        recorded = await self._after_sync([_inbound(0), _outbound(3)], [_inbound(5)])

        self.assertTrue(recorded)
        self.assertEqual(len(self._events(InboxEvent.NEEDS_REPLY)), 1)

    async def test_an_auto_reply_does_not_record(self):
        recorded = await self._after_sync(
            [_outbound(0)], [_inbound(5, kind=InboundKind.AUTO_REPLY)]
        )

        self.assertFalse(recorded)
        self.record.assert_not_awaited()

    async def test_an_inbound_after_archive_records(self):
        self.thread.archived_at = _at(2)

        recorded = await self._after_sync([_inbound(0)], [_inbound(5)])

        self.assertTrue(recorded)
        self.assertEqual(len(self._events(InboxEvent.NEEDS_REPLY)), 1)

    async def test_nothing_new_records_nothing(self):
        recorded = await self._after_sync([_inbound(0)], [])

        self.assertFalse(recorded)
        self.record.assert_not_awaited()
        self.messages.list_by_thread.assert_not_awaited()

    async def test_an_application_thread_never_records(self):
        self.thread.context_type = ContextType.APPLICATION

        recorded = await self._after_sync(
            [_outbound(0, sent_by=9)], [_inbound(5), _bounce(6)]
        )

        self.assertFalse(recorded)
        self.record.assert_not_awaited()
        self.messages.list_by_thread.assert_not_awaited()
        self.services.service_of.assert_not_awaited()

    async def test_the_service_comes_from_the_resolver(self):
        self.thread.context_type = ContextType.INQUIRIES_INBOX
        self.services.service_of.return_value = InboxService.INQUIRIES

        await self._after_sync([], [_inbound(0)])

        self.services.service_of.assert_awaited_once_with(self.session, self.thread)
        (event,) = self._events(InboxEvent.NEEDS_REPLY)
        self.assertEqual(event["details"]["service"], InboxService.INQUIRIES)

    async def test_from_names_the_newest_human_inbound(self):
        await self._after_sync(
            [],
            [_inbound(0, sender="first@ext.com"), _inbound(4, sender="last@ext.com")],
        )

        (event,) = self._events(InboxEvent.NEEDS_REPLY)
        self.assertEqual(event["details"]["from"], "last@ext.com")

    async def test_a_bounce_records_bounced_for_the_newest_earlier_sender(self):
        older = _outbound(0, sent_by=8, subject="Old")
        newer = _outbound(10, sent_by=9, subject="Your interview")
        later = _outbound(30, sent_by=10, subject="After the bounce")
        bounce = _bounce(20, failed="Asker <asker@ext.com>")

        recorded = await self._after_sync([older, newer, later], [bounce])

        self.assertFalse(recorded)
        self.record.assert_awaited_once_with(
            self.session,
            subject_type=INBOX_SUBJECT_TYPE,
            subject_id=77,
            actor_id=None,
            event_type=InboxEvent.BOUNCED,
            details={
                "bouncedTo": "asker@ext.com",
                "subject": "Your interview",
                "senderUserId": 9,
            },
        )

    async def test_a_bounce_with_no_known_sender_records_nothing(self):
        await self._after_sync(
            [_outbound(0, sent_by=8), _outbound(2, sent_by=None)], [_bounce(5)]
        )

        self.record.assert_not_awaited()

    async def test_a_bounce_with_no_earlier_outbound_records_nothing(self):
        await self._after_sync([], [_bounce(5)])

        self.record.assert_not_awaited()

    async def test_a_bounce_naming_nobody_falls_back_to_the_original_recipients(self):
        await self._after_sync([_outbound(0, sent_by=9)], [_bounce(5, failed="")])

        (event,) = self._events(InboxEvent.BOUNCED)
        self.assertEqual(event["details"]["bouncedTo"], "asker@ext.com")

    async def test_mail_dated_before_the_archive_but_stored_after_it_records(self):
        self.thread.archived_at = _at(5)

        recorded = await self._after_sync([_inbound(0)], [_inbound(3, stored=8)])

        self.assertTrue(recorded)
        self.assertEqual(len(self._events(InboxEvent.NEEDS_REPLY)), 1)

    async def test_mail_dated_before_our_reply_but_stored_after_it_records(self):
        recorded = await self._after_sync(
            [_inbound(0), _outbound(3)], [_inbound(2, stored=6)]
        )

        self.assertTrue(recorded)
        self.assertEqual(len(self._events(InboxEvent.NEEDS_REPLY)), 1)

    async def test_a_legacy_bounce_without_a_kind_records_bounced_not_needs_reply(
        self,
    ):
        legacy = _inbound(
            5, kind=None, sender="mailer-daemon@x.com", failed="asker@ext.com"
        )

        recorded = await self._after_sync([_outbound(0, sent_by=9)], [legacy])

        self.assertFalse(recorded)
        (event,) = self._events(InboxEvent.BOUNCED)
        self.assertEqual(event["details"]["senderUserId"], 9)
        self.assertEqual(self._events(InboxEvent.NEEDS_REPLY), [])


if __name__ == "__main__":
    unittest.main()
