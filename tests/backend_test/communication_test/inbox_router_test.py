import unittest
from unittest.mock import AsyncMock, Mock

from sqlalchemy.exc import IntegrityError

from backend.common.communication_enums import ContextType
from backend.communication.inbox_aliases import InboxAliases
from backend.communication.inbox_router import InboxRouter, RouteResult

_MAILBOX = "Purrf@Example.com"
_OURS = {"mentorship-test@example.com", "notification-test@example.com"}


class _Nested:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


def _message(from_address, recipients, date, subject="Hello"):
    return {
        "gmail_message_id": f"m{date}",
        "from_address": from_address,
        "recipients": recipients,
        "subject": subject,
        "gmail_internal_date": str(date),
    }


class TestInboxRouter(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.gmail = Mock()
        self.gmail.owns_address.side_effect = lambda a: (a or "").lower() in _OURS
        self.gmail.list_thread_message_ids.return_value = ["m1"]
        self.gmail.list_send_as_addresses.return_value = {
            "purrf@example.com",
            "mentorship-test@example.com",
            "notification-test@example.com",
            "mentorship@example.com",
        }
        self.threads = AsyncMock()
        self.created = Mock(thread_id=7)
        self.threads.create.return_value = self.created
        self.aliases = InboxAliases(mentorship="mentorship-test@example.com")
        self.logger = Mock()
        self.session = AsyncMock()
        self.session.begin_nested = Mock(return_value=_Nested())
        self.router = InboxRouter(
            gmail_client=self.gmail,
            thread_repository=self.threads,
            aliases=self.aliases,
            logger=self.logger,
        )

    def _messages(self, *messages):
        self.gmail.list_thread_message_ids.return_value = [
            m["gmail_message_id"] for m in messages
        ]
        self.gmail.get_messages.return_value = list(messages)

    async def _route(self, gid="g1"):
        return await self.router.route(self.session, gid, _MAILBOX)

    async def test_mail_to_a_claimed_alias_creates_an_unassigned_inbox_thread(self):
        self._messages(
            _message(
                "Wang <w@ext.com>",
                ["mentorship-test@example.com", "purrf@example.com"],
                1000,
                subject="Question",
            )
        )
        result = await self._route()
        self.assertEqual(
            result,
            RouteResult(
                thread=self.created,
                unrouted=False,
                messages=self.gmail.get_messages.return_value,
            ),
        )
        self.threads.create.assert_awaited_once_with(
            self.session,
            user_id=None,
            gmail_thread_id="g1",
            subject="Question",
            context_type=ContextType.MENTORSHIP_INBOX,
            context_id=None,
        )
        self.gmail.get_messages.assert_called_once_with(["m1000"])

    async def test_routing_reads_the_earliest_inbound_message(self):
        later = _message("x@ext.com", ["someone@example.com"], 3000)
        first = _message("y@ext.com", ["mentorship-test@example.com"], 1000, "First")
        self._messages(later, first)
        result = await self._route()
        self.assertIs(result.thread, self.created)
        self.assertEqual(self.threads.create.await_args.kwargs["subject"], "First")
        # Every message in Gmail's order, handed on to the first sync.
        self.assertEqual(result.messages, [later, first])

    async def test_our_own_messages_are_ignored_when_picking_the_first(self):
        self._messages(
            _message("notification-test@example.com", ["x@ext.com"], 500),
            _message("x@ext.com", ["mentorship-test@example.com"], 1000, "Reply"),
        )
        result = await self._route()
        self.assertIs(result.thread, self.created)
        self.assertEqual(self.threads.create.await_args.kwargs["subject"], "Reply")

    async def test_mail_to_another_environments_alias_is_skipped_silently(self):
        self._messages(
            _message(
                "x@ext.com",
                ["notification-test@example.com", "purrf@example.com"],
                1000,
            )
        )
        result = await self._route()
        self.assertEqual(result, RouteResult(thread=None, unrouted=False))
        self.threads.create.assert_not_awaited()
        self.logger.warning.assert_not_called()

    async def test_mail_to_no_send_as_alias_is_unrouted_and_logged(self):
        self._messages(_message("Wang <w@ext.com>", ["someone@example.com"], 1000))
        result = await self._route("g-lost")
        self.assertEqual(result, RouteResult(thread=None, unrouted=True))
        self.threads.create.assert_not_awaited()
        self.logger.warning.assert_called_once()
        logged = " ".join(str(a) for a in self.logger.warning.call_args.args)
        self.assertIn("g-lost", logged)
        self.assertIn("w@ext.com", logged)

    async def test_primary_address_alone_in_delivered_to_is_unrouted(self):
        self._messages(
            _message("w@ext.com", ["someone@example.com", "purrf@example.com"], 1000)
        )
        result = await self._route()
        self.assertEqual(result, RouteResult(thread=None, unrouted=True))
        self.threads.create.assert_not_awaited()

    async def test_thread_with_only_our_messages_is_neither_created_nor_unrouted(self):
        self._messages(
            _message("mentorship-test@example.com", ["x@ext.com"], 1000),
        )
        result = await self._route()
        self.assertEqual(result, RouteResult(thread=None, unrouted=False))
        self.threads.create.assert_not_awaited()
        self.gmail.list_send_as_addresses.assert_not_called()
        self.logger.warning.assert_not_called()

    async def test_duplicate_create_returns_the_row_another_push_created(self):
        self._messages(_message("x@ext.com", ["mentorship-test@example.com"], 1000))
        self.threads.create.side_effect = IntegrityError(
            "insert", {}, Exception("uq_email_thread_gmail_thread_id")
        )
        existing = Mock(thread_id=3)
        self.threads.get_by_gmail_thread_id.return_value = existing
        result = await self._route()
        self.assertEqual(
            result,
            RouteResult(
                thread=existing,
                unrouted=False,
                messages=self.gmail.get_messages.return_value,
            ),
        )
        self.threads.get_by_gmail_thread_id.assert_awaited_once_with(self.session, "g1")
        self.session.begin_nested.assert_called_once()

    async def test_gmail_failure_propagates(self):
        self.gmail.list_thread_message_ids.side_effect = RuntimeError("503")
        with self.assertRaises(RuntimeError):
            await self._route()


if __name__ == "__main__":
    unittest.main()
