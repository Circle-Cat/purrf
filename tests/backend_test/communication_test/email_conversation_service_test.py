import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from backend.common.communication_enums import ContextType, EmailDirection
from backend.communication.email_conversation_service import EmailConversationService

SENDER = "recruiting@circlecat.org"


class TestEmailConversationService(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.gmail = Mock()
        # Stand-in for the real GmailClient.owns_address: "is this From one of
        # the addresses this mailbox sends as?". Address normalisation (case,
        # display names) is the client's job and is tested there; this fake only
        # has to be faithful enough to drive the direction branch.
        self.gmail.owns_address.side_effect = (
            lambda address: SENDER in (address or "").lower()
        )
        self.thread_repo = AsyncMock()
        self.message_repo = AsyncMock()
        self.session = Mock()
        self.service = EmailConversationService(
            gmail_client=self.gmail,
            thread_repository=self.thread_repo,
            message_repository=self.message_repo,
            sender_address=SENDER,
        )
        # Default for the sync tests: nothing stored yet. Individual tests
        # override this. Without it the AsyncMock returns a Mock, and
        # `gmail_id in known` would blow up.
        self.message_repo.list_gmail_message_ids_by_thread.return_value = set()

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
        # This service says which address it sends as; the transport holds no
        # default, so a missing sender would go out as the mailbox owner.
        self.assertEqual(kwargs["sender"], SENDER)

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

    def _msg(self, message_id, when, gmail_date=None):
        return SimpleNamespace(
            message_id=message_id,
            direction="inbound",
            from_address="cand@example.com",
            to_addresses="recruiting@circlecat.org",
            cc_addresses=None,
            subject="Hi",
            body_html="<p>hi</p>",
            body_text="hi",
            snippet="hi",
            sent_by_user_id=None,
            gmail_internal_date=gmail_date,
            created_at=when,
        )

    def _thread_row(self, thread_id, created_at):
        return SimpleNamespace(
            thread_id=thread_id,
            subject=f"t{thread_id}",
            synced_at=None,
            created_at=created_at,
        )

    async def test_list_conversation_orders_messages_newest_first(self):
        self.thread_repo.list_by_context.return_value = [
            self._thread_row(10, "2026-07-01T00:00:00Z")
        ]
        # The repository hands them over oldest first — that order is what the
        # reply headers depend on, so the display order is applied here instead.
        self.message_repo.list_by_thread.return_value = [
            self._msg(1, "2026-07-01T00:00:00Z"),
            self._msg(2, "2026-07-05T00:00:00Z"),
            self._msg(3, "2026-07-09T00:00:00Z"),
        ]

        threads = await self.service.list_conversation(
            self.session, ContextType.APPLICATION, 7
        )

        self.assertEqual([m.message_id for m in threads[0].messages], [3, 2, 1])

    async def test_list_conversation_orders_threads_by_latest_activity(self):
        # Thread 10 started first but 20 has the newer reply, so 20 goes on top —
        # ordering by the thread's own created_at would have pinned 10 there
        # forever, however recently it was replied to.
        self.thread_repo.list_by_context.return_value = [
            self._thread_row(10, "2026-07-01T00:00:00Z"),
            self._thread_row(20, "2026-07-02T00:00:00Z"),
        ]
        by_thread = {
            10: [
                self._msg(1, "2026-07-01T00:00:00Z"),
                self._msg(2, "2026-07-03T00:00:00Z"),
            ],
            20: [
                self._msg(3, "2026-07-02T00:00:00Z"),
                self._msg(4, "2026-07-08T00:00:00Z"),
            ],
        }
        self.message_repo.list_by_thread.side_effect = (
            lambda _session, thread_id: by_thread[thread_id]
        )

        threads = await self.service.list_conversation(
            self.session, ContextType.APPLICATION, 7
        )

        self.assertEqual([t.thread_id for t in threads], [20, 10])

    async def test_list_conversation_prefers_the_gmail_timestamp_for_ordering(self):
        # created_at is our insert time; a synced message's real send time is
        # the Gmail one, and a backfilled thread can have the two disagree.
        self.thread_repo.list_by_context.return_value = [
            self._thread_row(10, "2026-07-01T00:00:00Z"),
            self._thread_row(20, "2026-07-02T00:00:00Z"),
        ]
        by_thread = {
            10: [
                self._msg(1, "2026-07-20T00:00:00Z", gmail_date="2026-07-09T00:00:00Z")
            ],
            20: [
                self._msg(2, "2026-07-21T00:00:00Z", gmail_date="2026-07-03T00:00:00Z")
            ],
        }
        self.message_repo.list_by_thread.side_effect = (
            lambda _session, thread_id: by_thread[thread_id]
        )

        threads = await self.service.list_conversation(
            self.session, ContextType.APPLICATION, 7
        )

        self.assertEqual([t.thread_id for t in threads], [10, 20])

    async def test_list_conversation_sorts_an_empty_thread_by_its_own_timestamp(self):
        self.thread_repo.list_by_context.return_value = [
            self._thread_row(10, "2026-07-01T00:00:00Z"),
            self._thread_row(20, "2026-07-10T00:00:00Z"),
        ]
        by_thread = {10: [self._msg(1, "2026-07-05T00:00:00Z")], 20: []}
        self.message_repo.list_by_thread.side_effect = (
            lambda _session, thread_id: by_thread[thread_id]
        )

        threads = await self.service.list_conversation(
            self.session, ContextType.APPLICATION, 7
        )

        self.assertEqual([t.thread_id for t in threads], [20, 10])

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
            "cc_addresses": "watcher@example.com",
            "subject": "Re: Hi",
            "html": "<p>body</p>",
            "plain": "body",
            "snippet": "body",
            "gmail_internal_date": "1700000000000",
        }

    async def test_sync_thread_fetches_bodies_only_for_new_messages(self):
        self.gmail.list_thread_message_ids.return_value = ["g1", "g2"]
        self.message_repo.list_gmail_message_ids_by_thread.return_value = {"g1"}
        self.gmail.get_message.return_value = self._fetched("g2", "cand@example.com")
        self.message_repo.create.return_value = SimpleNamespace(message_id=2)

        created = await self.service.sync_thread(self.session, self._thread())

        self.gmail.list_thread_message_ids.assert_called_once_with("gt1")
        # The already-stored g1 costs nothing: no body fetch, no insert.
        self.gmail.get_message.assert_called_once_with("g2")
        self.message_repo.create.assert_awaited_once()
        _, mkw = self.message_repo.create.call_args
        self.assertEqual(mkw["thread_id"], 10)
        self.assertEqual(mkw["gmail_message_id"], "g2")
        self.assertEqual(mkw["direction"], EmailDirection.INBOUND)
        self.assertEqual(mkw["from_address"], "cand@example.com")
        self.assertEqual(mkw["to_addresses"], "someone@example.com")
        self.assertEqual(mkw["cc_addresses"], "watcher@example.com")
        self.assertEqual(mkw["subject"], "Re: Hi")
        self.assertEqual(mkw["body_html"], "<p>body</p>")
        self.assertEqual(mkw["body_text"], "body")
        self.assertEqual(mkw["snippet"], "body")
        self.assertEqual(mkw["rfc822_message_id"], "<g2@mail>")
        self.thread_repo.mark_synced.assert_awaited_once_with(self.session, 10)
        self.assertEqual(len(created), 1)
        self.assertIs(created[0], self.message_repo.create.return_value)

    async def test_sync_thread_steady_state_costs_one_call_each_side(self):
        # The common case: nothing new. This is the whole point of the change —
        # a 30-message thread must not fetch 30 bodies to discover 0 new ones.
        self.gmail.list_thread_message_ids.return_value = ["g1", "g2", "g3"]
        self.message_repo.list_gmail_message_ids_by_thread.return_value = {
            "g1",
            "g2",
            "g3",
        }

        created = await self.service.sync_thread(self.session, self._thread())

        self.assertEqual(self.gmail.list_thread_message_ids.call_count, 1)
        self.gmail.get_message.assert_not_called()
        self.message_repo.create.assert_not_awaited()
        self.thread_repo.mark_synced.assert_awaited_once_with(self.session, 10)
        self.assertEqual(created, [])

    async def test_sync_thread_queries_known_ids_exactly_once(self):
        # Guards against an N+1 regression: one existence query per THREAD,
        # never one per message.
        self.gmail.list_thread_message_ids.return_value = ["g1", "g2", "g3"]
        self.message_repo.list_gmail_message_ids_by_thread.return_value = set()
        self.gmail.get_message.side_effect = [
            self._fetched("g1", "cand@example.com"),
            self._fetched("g2", "cand@example.com"),
            self._fetched("g3", "cand@example.com"),
        ]
        self.message_repo.create.side_effect = [
            SimpleNamespace(message_id=1),
            SimpleNamespace(message_id=2),
            SimpleNamespace(message_id=3),
        ]

        await self.service.sync_thread(self.session, self._thread())

        self.message_repo.list_gmail_message_ids_by_thread.assert_awaited_once_with(
            self.session, 10
        )

    async def test_sync_thread_preserves_gmail_order(self):
        self.gmail.list_thread_message_ids.return_value = ["g1", "g2", "g3"]
        self.message_repo.list_gmail_message_ids_by_thread.return_value = {"g2"}
        self.gmail.get_message.side_effect = [
            self._fetched("g1", "cand@example.com"),
            self._fetched("g3", "cand@example.com"),
        ]
        self.message_repo.create.side_effect = [
            SimpleNamespace(message_id=1),
            SimpleNamespace(message_id=3),
        ]

        created = await self.service.sync_thread(self.session, self._thread())

        self.assertEqual(
            [call.args[0] for call in self.gmail.get_message.call_args_list],
            ["g1", "g3"],
        )
        self.assertEqual([entity.message_id for entity in created], [1, 3])

    async def test_sync_thread_classifies_outbound_by_sender_even_with_display_name(
        self,
    ):
        self.gmail.list_thread_message_ids.return_value = ["g9"]
        self.message_repo.list_gmail_message_ids_by_thread.return_value = set()
        self.gmail.get_message.return_value = self._fetched(
            "g9", f"Circle Cat Recruiting <{SENDER}>"
        )
        self.message_repo.create.return_value = SimpleNamespace(message_id=3)

        await self.service.sync_thread(self.session, self._thread())

        _, mkw = self.message_repo.create.call_args
        self.assertEqual(mkw["direction"], EmailDirection.OUTBOUND)
        self.assertEqual(mkw["gmail_internal_date"].year, 2023)

    async def test_sync_thread_asks_the_transport_which_addresses_are_ours(self):
        # Direction must not be a string compare against our own one address:
        # a second send-as alias on the same mailbox is still us. The transport
        # owns that question, and this service must take its answer.
        self.gmail.list_thread_message_ids.return_value = ["g9"]
        self.message_repo.list_gmail_message_ids_by_thread.return_value = set()
        self.gmail.get_message.return_value = self._fetched(
            "g9", "notification@circlecat.org"
        )
        self.gmail.owns_address.side_effect = None
        self.gmail.owns_address.return_value = True
        self.message_repo.create.return_value = SimpleNamespace(message_id=4)

        await self.service.sync_thread(self.session, self._thread())

        self.gmail.owns_address.assert_called_with("notification@circlecat.org")
        _, mkw = self.message_repo.create.call_args
        self.assertEqual(mkw["direction"], EmailDirection.OUTBOUND)

    async def test_sync_thread_propagates_a_failed_body_fetch(self):
        # A message deleted between listing and fetching yields a 404 ->
        # RuntimeError. We deliberately do NOT swallow it: a silent partial
        # sync ("looked fine, quietly missed a mail") is worse than a failed
        # Refresh the user can retry, and the retry self-heals because the id
        # is gone from the next listing.
        self.gmail.list_thread_message_ids.return_value = ["g1"]
        self.message_repo.list_gmail_message_ids_by_thread.return_value = set()
        self.gmail.get_message.side_effect = RuntimeError("Gmail API error")

        with self.assertRaises(RuntimeError):
            await self.service.sync_thread(self.session, self._thread())

        self.message_repo.create.assert_not_awaited()
        self.thread_repo.mark_synced.assert_not_awaited()

    async def test_sync_context_syncs_each_thread(self):
        self.thread_repo.list_by_context.return_value = [
            SimpleNamespace(thread_id=10, gmail_thread_id="gtA"),
            SimpleNamespace(thread_id=11, gmail_thread_id="gtB"),
        ]
        self.gmail.list_thread_message_ids.side_effect = [["gA1"], ["gB1"]]
        self.message_repo.list_gmail_message_ids_by_thread.return_value = set()
        self.gmail.get_message.side_effect = [
            self._fetched("gA1", "cand-a@example.com"),
            self._fetched("gB1", "cand-b@example.com"),
        ]
        self.message_repo.create.side_effect = [
            SimpleNamespace(message_id=201),
            SimpleNamespace(message_id=202),
        ]
        result = await self.service.sync_context(
            self.session, ContextType.APPLICATION, 7
        )
        self.assertEqual(self.gmail.list_thread_message_ids.call_count, 2)
        self.assertEqual(len(result), 2)
        self.assertEqual({message.message_id for message in result}, {201, 202})

    async def test_sender_address_exposes_company_sender(self):
        self.assertEqual(self.service.sender_address, SENDER)


if __name__ == "__main__":
    unittest.main()
