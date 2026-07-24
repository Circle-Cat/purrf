import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from backend.common.communication_enums import ContextType, EmailDirection
from backend.communication.email_conversation_service import EmailConversationService

SENDER = "recruiting@circlecat.org"


class TestEmailConversationService(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.gmail = Mock()
        self.gmail.sender_address = SENDER
        self.thread_repo = AsyncMock()
        self.message_repo = AsyncMock()
        self.session = Mock()
        self.service = EmailConversationService(
            gmail_client=self.gmail,
            thread_repository=self.thread_repo,
            message_repository=self.message_repo,
            sender_address=SENDER,
        )

    # ---- send: new thread ---------------------------------------------

    async def test_send_new_thread_calls_gmail_then_persists(self):
        self.gmail.send_message.return_value = {
            "gmail_message_id": "g1",
            "gmail_thread_id": "gt1",
            "rfc822_message_id": "<r1@mail>",
        }
        self.thread_repo.create.return_value = SimpleNamespace(
            thread_id=10, gmail_thread_id="gt1"
        )
        self.message_repo.create.return_value = SimpleNamespace(message_id=99)

        result = await self.service.send(
            self.session,
            user_id=5,
            context_type=ContextType.APPLICATION,
            context_id=7,
            to=["cand@example.com"],
            cc=[],
            subject="Hi",
            body="<p>hello</p>",
            sender_user_id=3,
        )

        # Gmail is called first, as a new thread (no thread_id).
        self.gmail.send_message.assert_called_once()
        _, kwargs = self.gmail.send_message.call_args
        self.assertIsNone(kwargs.get("thread_id"))

        self.thread_repo.create.assert_awaited_once()
        _, tkw = self.thread_repo.create.call_args
        self.assertEqual(tkw["user_id"], 5)
        self.assertEqual(tkw["gmail_thread_id"], "gt1")
        self.assertEqual(tkw["context_type"], ContextType.APPLICATION)
        self.assertEqual(tkw["context_id"], 7)

        self.message_repo.create.assert_awaited_once()
        _, mkw = self.message_repo.create.call_args
        self.assertEqual(mkw["thread_id"], 10)
        self.assertEqual(mkw["gmail_message_id"], "g1")
        self.assertEqual(mkw["direction"], EmailDirection.OUTBOUND)
        self.assertEqual(mkw["from_address"], SENDER)
        self.assertEqual(mkw["to_addresses"], "cand@example.com")
        self.assertEqual(mkw["body_html"], "<p>hello</p>")
        self.assertEqual(mkw["rfc822_message_id"], "<r1@mail>")
        self.assertEqual(mkw["sent_by_user_id"], 3)

        self.assertIs(result, self.message_repo.create.return_value)

    async def test_send_does_not_persist_when_gmail_fails(self):
        self.gmail.send_message.side_effect = RuntimeError("gmail down")
        with self.assertRaises(RuntimeError):
            await self.service.send(
                self.session,
                user_id=5,
                context_type=ContextType.APPLICATION,
                context_id=7,
                to=["cand@example.com"],
                cc=[],
                subject="Hi",
                body="<p>x</p>",
                sender_user_id=3,
            )
        self.thread_repo.create.assert_not_awaited()
        self.message_repo.create.assert_not_awaited()

    async def test_send_multiple_cc_joined_into_header(self):
        self.gmail.send_message.return_value = {
            "gmail_message_id": "g1",
            "gmail_thread_id": "gt1",
            "rfc822_message_id": "<r1@mail>",
        }
        self.thread_repo.create.return_value = SimpleNamespace(thread_id=10)
        self.message_repo.create.return_value = SimpleNamespace(message_id=99)
        await self.service.send(
            self.session,
            user_id=5,
            context_type=ContextType.APPLICATION,
            context_id=7,
            to=["a@example.com"],
            cc=["b@example.com", "c@example.com"],
            subject="Hi",
            body="<p>x</p>",
            sender_user_id=3,
        )
        _, mkw = self.message_repo.create.call_args
        self.assertEqual(mkw["cc_addresses"], "b@example.com, c@example.com")

    # ---- send: reply --------------------------------------------------

    async def test_send_reply_uses_existing_thread_and_headers(self):
        self.thread_repo.get.return_value = SimpleNamespace(
            thread_id=10,
            gmail_thread_id="gt1",
            context_type=ContextType.APPLICATION,
            context_id=7,
        )
        self.message_repo.list_by_thread.return_value = [
            SimpleNamespace(rfc822_message_id="<r1@mail>"),
            SimpleNamespace(rfc822_message_id="<r2@mail>"),
        ]
        self.gmail.send_message.return_value = {
            "gmail_message_id": "g3",
            "gmail_thread_id": "gt1",
            "rfc822_message_id": "<r3@mail>",
        }
        self.message_repo.create.return_value = SimpleNamespace(message_id=100)

        await self.service.send(
            self.session,
            user_id=5,
            context_type=ContextType.APPLICATION,
            context_id=7,
            to=["cand@example.com"],
            cc=[],
            subject="Re: Hi",
            body="<p>reply</p>",
            sender_user_id=3,
            thread_id=10,
        )

        _, kwargs = self.gmail.send_message.call_args
        self.assertEqual(kwargs["thread_id"], "gt1")
        self.assertEqual(kwargs["in_reply_to"], "<r2@mail>")
        self.assertEqual(kwargs["references"], "<r1@mail> <r2@mail>")
        # Existing thread: not re-created.
        self.thread_repo.create.assert_not_awaited()
        _, mkw = self.message_repo.create.call_args
        self.assertEqual(mkw["thread_id"], 10)

    async def test_send_reply_rejects_thread_from_other_context(self):
        # Replying into a thread that belongs to a different (context_type,
        # context_id) must be refused — no cross-context leakage, no send.
        self.thread_repo.get.return_value = SimpleNamespace(
            thread_id=10,
            gmail_thread_id="gt1",
            context_type=ContextType.APPLICATION,
            context_id=999,
        )
        with self.assertRaises(ValueError):
            await self.service.send(
                self.session,
                user_id=5,
                context_type=ContextType.APPLICATION,
                context_id=7,
                to=["cand@example.com"],
                cc=[],
                subject="Re: Hi",
                body="<p>x</p>",
                sender_user_id=3,
                thread_id=10,
            )
        self.gmail.send_message.assert_not_called()
        self.message_repo.create.assert_not_awaited()

    # ---- list_conversation --------------------------------------------

    async def test_list_conversation_assembles_threads_with_messages(self):
        self.thread_repo.list_by_context.return_value = [
            SimpleNamespace(
                thread_id=10,
                subject="Hi",
                synced_at=None,
                created_at="2026-07-23T00:00:00Z",
            ),
        ]
        self.message_repo.list_by_thread.return_value = [
            SimpleNamespace(
                message_id=1,
                direction="outbound",
                from_address="recruiting@circlecat.org",
                to_addresses="cand@example.com",
                cc_addresses=None,
                subject="Hi",
                body_html="<p>hi</p>",
                body_text="hi",
                snippet="hi",
                sent_by_user_id=3,
                gmail_internal_date=None,
                created_at="2026-07-23T00:00:00Z",
            ),
        ]
        threads = await self.service.list_conversation(
            self.session, ContextType.APPLICATION, 7
        )
        self.assertEqual(len(threads), 1)
        self.assertEqual(threads[0].thread_id, 10)
        self.assertEqual(len(threads[0].messages), 1)
        self.assertEqual(threads[0].messages[0].message_id, 1)
        self.assertEqual(threads[0].messages[0].direction, "outbound")
        self.message_repo.list_by_thread.assert_awaited_once_with(self.session, 10)

    # ---- sync ---------------------------------------------------------

    def _thread(self):
        return SimpleNamespace(thread_id=10, gmail_thread_id="gt1")

    def _fetched(self, gmail_message_id, from_address):
        return {
            "gmail_message_id": gmail_message_id,
            "gmail_thread_id": "gt1",
            "rfc822_message_id": f"<{gmail_message_id}@mail>",
            "from_address": from_address,
            "to_addresses": "someone@example.com",
            "cc_addresses": None,
            "subject": "Re: Hi",
            "html": "<p>body</p>",
            "plain": "body",
            "snippet": "body",
            "gmail_internal_date": "1700000000000",
        }

    async def test_sync_thread_persists_only_new_messages(self):
        self.gmail.get_thread.return_value = [
            self._fetched("g1", SENDER),
            self._fetched("g2", "cand@example.com"),
        ]
        # g1 already stored, g2 is new.
        self.message_repo.get_by_gmail_message_id.side_effect = [
            SimpleNamespace(message_id=1),
            None,
        ]
        self.message_repo.create.return_value = SimpleNamespace(message_id=2)

        created = await self.service.sync_thread(self.session, self._thread())

        self.gmail.get_thread.assert_called_once_with("gt1")
        self.message_repo.create.assert_awaited_once()
        _, mkw = self.message_repo.create.call_args
        self.assertEqual(mkw["gmail_message_id"], "g2")
        self.assertEqual(mkw["direction"], EmailDirection.INBOUND)
        self.thread_repo.mark_synced.assert_awaited_once_with(self.session, 10)
        self.assertEqual(len(created), 1)
        self.assertIs(created[0], self.message_repo.create.return_value)
        self.assertEqual(created[0].message_id, 2)

    async def test_sync_thread_classifies_outbound_by_sender_even_with_display_name(
        self,
    ):
        self.gmail.get_thread.return_value = [
            self._fetched("g9", f"Circle Cat Recruiting <{SENDER}>"),
        ]
        self.message_repo.get_by_gmail_message_id.return_value = None
        self.message_repo.create.return_value = SimpleNamespace(message_id=3)

        await self.service.sync_thread(self.session, self._thread())

        _, mkw = self.message_repo.create.call_args
        self.assertEqual(mkw["direction"], EmailDirection.OUTBOUND)
        self.assertEqual(mkw["gmail_internal_date"].year, 2023)

    async def test_sync_context_syncs_each_thread(self):
        self.thread_repo.list_by_context.return_value = [
            SimpleNamespace(thread_id=10, gmail_thread_id="gtA"),
            SimpleNamespace(thread_id=11, gmail_thread_id="gtB"),
        ]
        self.gmail.get_thread.side_effect = [
            [self._fetched("gA1", "cand-a@example.com")],
            [self._fetched("gB1", "cand-b@example.com")],
        ]
        self.message_repo.get_by_gmail_message_id.return_value = None
        self.message_repo.create.side_effect = [
            SimpleNamespace(message_id=201),
            SimpleNamespace(message_id=202),
        ]
        result = await self.service.sync_context(
            self.session, ContextType.APPLICATION, 7
        )
        self.assertEqual(self.gmail.get_thread.call_count, 2)
        self.assertEqual(len(result), 2)
        self.assertEqual({message.message_id for message in result}, {201, 202})

    async def test_sender_address_exposes_company_sender(self):
        self.assertEqual(self.service.sender_address, SENDER)


if __name__ == "__main__":
    unittest.main()
