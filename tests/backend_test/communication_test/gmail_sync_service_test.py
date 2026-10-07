import asyncio
import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock

from backend.common.exceptions import (
    GmailNotFoundError,
    GmailUnavailableError,
    HistoryExpiredError,
    RateLimitedError,
)
from backend.communication.gmail_sync_service import GmailSyncService, PushOutcome
from backend.communication.inbox_router import RouteResult


class _Nested:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False  # let the exception propagate like SQLAlchemy does


class _FakeDatabase:
    def __init__(self, session):
        self.session_object = session

    def session(self):
        return self

    async def __aenter__(self):
        return self.session_object

    async def __aexit__(self, *exc_info):
        return False


class TestGmailSyncService(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.gmail = Mock()
        self.gmail.get_profile.return_value = {
            "email_address": "purrf@example.com",
            "history_id": 500,
        }
        self.state = Mock(id=3, last_history_id=100, last_error=None)
        self.states = AsyncMock()
        self.states.get_for_update.return_value = self.state
        self.states.get.return_value = self.state
        self.threads = AsyncMock()
        self.handler = AsyncMock()
        self.handler.sync_tracked_thread.return_value = 1
        self.registry = Mock()
        self.registry.get.side_effect = (
            lambda ct: self.handler if ct == "application" else None
        )
        self.registry.handlers.return_value = [self.handler]
        self.alerts = AsyncMock()
        self.session = AsyncMock()
        self.session.begin_nested = Mock(return_value=_Nested())
        self.fresh_session = AsyncMock()
        self.logger = Mock()
        self.router = AsyncMock()
        self.router.route.return_value = RouteResult(thread=None, unrouted=False)
        self.service = self._service("projects/p/topics/gmail")

    def _service(self, watch_topic):
        return GmailSyncService(
            gmail_client=self.gmail,
            state_repository=self.states,
            thread_repository=self.threads,
            context_registry=self.registry,
            ops_alerts=self.alerts,
            watch_topic=watch_topic,
            database=_FakeDatabase(self.fresh_session),
            logger=self.logger,
            inbox_router=self.router,
        )

    def _tracked(self, gid, context_type="application"):
        return Mock(gmail_thread_id=gid, context_type=context_type)

    def _history(self, thread_map, history_id=150):
        self.gmail.list_history.return_value = {
            "history_id": history_id,
            "thread_ids": set(thread_map),
        }
        self.threads.get_by_gmail_thread_id.side_effect = (
            lambda session, gid: thread_map[gid]
        )

    def _three_threads(self):
        self.t1 = self._tracked("t1")
        self._history({
            "t1": self.t1,
            "t2": None,
            "t3": self._tracked("t3", "activity"),
        })

    def _alert_kinds(self):
        return [c.kwargs["kind"] for c in self.alerts.raise_alert.await_args_list]

    async def test_push_for_another_mailbox_is_acked_untouched(self):
        outcome = await self.service.handle_push(self.session, "other@example.com", 900)
        self.assertEqual(outcome, PushOutcome.ACK)
        self.states.get_for_update.assert_not_called()

    async def test_first_push_initialises_the_cursor_without_backfill(self):
        self.states.get_for_update.return_value = None
        outcome = await self.service.handle_push(self.session, "purrf@example.com", 900)
        self.states.create.assert_awaited_once_with(
            self.session, "purrf@example.com", 500
        )
        self.gmail.list_history.assert_not_called()
        self.session.commit.assert_awaited()
        self.assertEqual(outcome, PushOutcome.ACK)

    async def test_row_without_a_cursor_is_initialised_like_a_first_push(self):
        # renew_watch creates such a row when the very first watch call fails.
        self.state.last_history_id = None
        outcome = await self.service.handle_push(self.session, "purrf@example.com", 900)
        self.assertEqual(self.state.last_history_id, 500)
        self.gmail.list_history.assert_not_called()
        self.assertEqual(outcome, PushOutcome.ACK)

    async def test_push_address_is_compared_case_insensitively(self):
        self._three_threads()
        outcome = await self.service.handle_push(self.session, "PURRF@Example.com", 120)
        self.assertEqual(outcome, PushOutcome.ACK)
        self.gmail.list_history.assert_called_once_with(100)

    async def test_stale_push_does_not_call_gmail(self):
        outcome = await self.service.handle_push(self.session, "purrf@example.com", 100)
        self.gmail.list_history.assert_not_called()
        self.assertEqual(outcome, PushOutcome.ACK)
        self.session.commit.assert_awaited()
        self.states.get_for_update.assert_awaited()

    async def test_push_syncs_only_tracked_threads_with_a_handler(self):
        self._three_threads()
        await self.service.handle_push(self.session, "purrf@example.com", 120)
        self.handler.sync_tracked_thread.assert_awaited_once_with(self.session, self.t1)
        self.gmail.list_history.assert_called_once_with(100)
        self.assertEqual(self.states.get_for_update.await_count, 2)
        self.states.get.assert_not_called()

    async def test_cursor_moves_to_the_response_history_id(self):
        self._three_threads()
        await self.service.handle_push(self.session, "purrf@example.com", 120)
        self.assertEqual(self.state.last_history_id, 150)
        self.assertIsNone(self.state.last_error)
        self.session.commit.assert_awaited()

    async def test_cursor_never_moves_backwards(self):
        self._history({}, history_id=90)
        await self.service.handle_push(self.session, "purrf@example.com", 120)
        self.assertEqual(self.state.last_history_id, 100)

    async def test_one_failing_thread_does_not_block_the_others_or_the_cursor(self):
        t1, t2 = self._tracked("t1"), self._tracked("t2")
        self._history({"t1": t1, "t2": t2})

        async def sync(session, thread):
            if thread is t1:
                raise RuntimeError("boom")
            return 1

        self.handler.sync_tracked_thread.side_effect = sync
        outcome = await self.service.handle_push(self.session, "purrf@example.com", 120)
        self.handler.sync_tracked_thread.assert_any_await(self.session, t2)
        self.assertEqual(self.state.last_history_id, 150)
        self.assertEqual(outcome, PushOutcome.ACK)

    async def test_untracked_thread_is_routed_with_the_mailbox_address(self):
        self._three_threads()
        await self.service.handle_push(self.session, "purrf@example.com", 120)
        self.router.route.assert_awaited_once_with(
            self.session, "t2", "purrf@example.com"
        )

    async def test_a_routed_thread_is_synced_by_its_handler(self):
        created = self._tracked("t2")
        self._history({"t2": None})
        self.router.route.return_value = RouteResult(thread=created, unrouted=False)
        summary = await self.service.catch_up(self.session)
        self.handler.sync_tracked_thread.assert_awaited_once_with(
            self.session, created
        )
        self.assertEqual(
            summary, {"threads": 1, "newMessages": 1, "failed": 0, "unrouted": []}
        )

    async def test_unrouted_mail_raises_one_alert_before_the_commit(self):
        self._history({"u1": None, "u2": None})
        self.router.route.return_value = RouteResult(thread=None, unrouted=True)
        order = []
        self.alerts.raise_alert.side_effect = lambda *a, **k: order.append(
            k["kind"]
        )
        self.session.commit.side_effect = lambda: order.append("commit")
        summary = await self.service.catch_up(self.session)
        self.assertEqual(summary["unrouted"], ["u1", "u2"])
        self.assertEqual(order, ["unrouted_mail", "commit"])
        detail = self.alerts.raise_alert.await_args.kwargs["detail"]
        self.assertIn("u1", detail)
        self.assertIn("u2", detail)
        self.assertEqual(self.state.last_history_id, 150)

    async def test_unrouted_alert_follows_the_transient_alert(self):
        self._failing_threads(RateLimitedError("429"), "t-rate")
        self.threads.get_by_gmail_thread_id.side_effect = lambda session, gid: (
            None if gid == "u1" else self._tracked(gid)
        )
        self.gmail.list_history.return_value["thread_ids"].add("u1")
        self.router.route.return_value = RouteResult(thread=None, unrouted=True)
        await self.service.handle_push(self.session, "purrf@example.com", 120)
        self.assertEqual(self._alert_kinds(), ["sync_failed", "unrouted_mail"])

    async def test_no_unrouted_alert_for_mail_skipped_as_another_environments(self):
        self._history({"o1": None})
        await self.service.handle_push(self.session, "purrf@example.com", 120)
        self.alerts.raise_alert.assert_not_awaited()

    async def test_a_failing_route_counts_as_transient_and_the_cursor_moves(self):
        ok = self._tracked("ok")
        self._history({"bad": None, "ok": ok})
        self.router.route.side_effect = RateLimitedError("429")
        outcome = await self.service.handle_push(self.session, "purrf@example.com", 120)
        self.assertEqual(outcome, PushOutcome.ACK)
        self.handler.sync_tracked_thread.assert_awaited_once_with(self.session, ok)
        self.assertEqual(self._alert_kinds(), ["sync_failed"])
        self.assertIn("bad", self.state.last_error)
        self.assertEqual(self.state.last_history_id, 150)

    async def test_a_route_404_skips_the_thread_without_alerting(self):
        self._history({"gone": None})
        self.router.route.side_effect = GmailNotFoundError("404")
        summary = await self.service.catch_up(self.session)
        self.assertEqual(summary["failed"], 1)
        self.alerts.raise_alert.assert_not_awaited()
        self.assertEqual(self.state.last_history_id, 150)

    async def test_push_on_an_expired_cursor_starts_a_resync_without_running_it(self):
        self.gmail.list_history.side_effect = HistoryExpiredError("gone")

        outcome = await self.service.handle_push(self.session, "purrf@example.com", 120)

        self.assertEqual(outcome, PushOutcome.RESYNC)
        self.handler.resync_all.assert_not_awaited()
        self.assertEqual(self._alert_kinds(), ["history_expired"])
        self.assertIn(
            "full resync", self.alerts.raise_alert.await_args.kwargs["detail"]
        )
        self.assertIn("started", self.alerts.raise_alert.await_args.kwargs["detail"])
        self.assertEqual(self.state.last_history_id, 500)
        self.assertIsInstance(self.state.last_push_at, datetime)
        self.session.commit.assert_awaited()

    async def test_push_on_an_expired_cursor_never_moves_it_backwards(self):
        self.state.last_history_id = 900
        self.gmail.list_history.side_effect = HistoryExpiredError("gone")
        await self.service.handle_push(self.session, "purrf@example.com", 950)
        self.assertEqual(self.state.last_history_id, 900)

    async def test_push_on_an_expired_cursor_retries_when_the_snapshot_is_unavailable(
        self,
    ):
        await self.service.mailbox_address()
        self.gmail.list_history.side_effect = HistoryExpiredError("gone")
        self.gmail.get_profile.side_effect = GmailUnavailableError("503")
        outcome = await self.service.handle_push(self.session, "purrf@example.com", 120)
        self.assertEqual(outcome, PushOutcome.RETRY)
        self.assertEqual(self.state.last_history_id, 100)
        self.handler.resync_all.assert_not_awaited()

    async def test_scheduled_resync_runs_every_handler_and_keeps_the_cursor(self):
        self.state.last_history_id = 500
        self.handler.resync_all.return_value = {"scanned": 3}

        result = await self.service.run_scheduled_resync(self.session)

        self.handler.resync_all.assert_awaited_once_with(self.session)
        self.assertEqual(result, {"handlers": [{"scanned": 3}]})
        self.assertEqual(self.state.last_history_id, 500)
        self.alerts.raise_alert.assert_not_awaited()
        self.gmail.list_history.assert_not_called()

    async def test_scheduled_resync_failure_alerts_for_a_manual_resync(self):
        self.handler.resync_all.side_effect = RuntimeError("db down")
        with self.assertRaises(RuntimeError):
            await self.service.run_scheduled_resync(self.session)
        self.assertEqual(self._alert_kinds(), ["sync_failed"])
        detail = self.alerts.raise_alert.await_args.kwargs["detail"]
        self.assertIn("full resync failed: db down", detail)
        self.assertIn("trigger a manual full resync", detail)
        self.assertIn("db down", self.state.last_error)
        self.session.rollback.assert_awaited()
        self.session.commit.assert_awaited()

    async def test_cancelled_resync_still_records_and_alerts(self):
        self.handler.resync_all.side_effect = asyncio.CancelledError()
        with self.assertRaises(asyncio.CancelledError):
            await self.service.run_scheduled_resync(self.session)
        self.assertEqual(self._alert_kinds(), ["sync_failed"])
        self.assertIn("CancelledError", self.state.last_error)

    async def test_resync_failure_alerts_from_a_fresh_session_when_its_own_is_unusable(
        self,
    ):
        self.handler.resync_all.side_effect = RuntimeError("db down")
        self.session.rollback.side_effect = RuntimeError("connection closed")
        with self.assertRaises(RuntimeError) as raised:
            await self.service.run_scheduled_resync(self.session)
        self.assertEqual(str(raised.exception), "db down")
        self.assertIs(self.alerts.raise_alert.await_args.args[0], self.fresh_session)
        self.fresh_session.commit.assert_awaited()

    async def test_catch_up_on_an_expired_cursor_resyncs_from_a_prior_snapshot(self):
        await self.service.mailbox_address()
        self.gmail.list_history.side_effect = HistoryExpiredError("gone")
        order = Mock()
        order.attach_mock(self.gmail.get_profile, "get_profile")
        order.attach_mock(self.handler.resync_all, "resync_all")
        cursor_during_resync = []

        async def resync_all(session):
            cursor_during_resync.append(self.state.last_history_id)
            session.commit.assert_awaited()

        self.handler.resync_all.side_effect = resync_all

        await self.service.catch_up(self.session)

        self.assertEqual(self._alert_kinds(), ["history_expired"])
        self.handler.resync_all.assert_awaited_once_with(self.session)
        self.assertEqual(self.state.last_history_id, 500)
        self.assertEqual(cursor_during_resync, [500])
        self.assertEqual(
            [c[0] for c in order.mock_calls], ["get_profile", "resync_all"]
        )

    async def test_catch_up_failed_full_resync_alerts_for_a_manual_resync(self):
        self.gmail.list_history.side_effect = HistoryExpiredError("gone")
        self.handler.resync_all.side_effect = RuntimeError("db down")
        with self.assertRaises(RuntimeError):
            await self.service.catch_up(self.session)
        self.assertEqual(self._alert_kinds(), ["history_expired", "sync_failed"])
        detail = self.alerts.raise_alert.await_args.kwargs["detail"]
        self.assertIn("db down", detail)
        self.assertIn("manual full resync", detail)
        self.assertIn("db down", self.state.last_error)
        self.assertEqual(self.state.last_history_id, 500)
        self.session.commit.assert_awaited()

    async def test_manual_full_resync_does_not_alert(self):
        self.handler.resync_all.return_value = {"scanned": 2}
        result = await self.service.full_resync(self.session, alert=False)
        self.alerts.raise_alert.assert_not_awaited()
        self.handler.resync_all.assert_awaited_once_with(self.session)
        self.assertEqual(self.state.last_history_id, 500)
        self.assertEqual(result, {"handlers": [{"scanned": 2}]})

    async def test_manual_full_resync_without_a_row_creates_it_at_the_snapshot(self):
        self.states.get_for_update.side_effect = [None, self.state, self.state]
        self.states.create.return_value = self.state
        await self.service.full_resync(self.session, alert=False)
        self.states.create.assert_awaited_once_with(
            self.session, "purrf@example.com", 500
        )

    async def test_failed_manual_full_resync_still_alerts_sync_failed(self):
        self.handler.resync_all.side_effect = RuntimeError("db down")
        with self.assertRaises(RuntimeError):
            await self.service.full_resync(self.session, alert=False)
        self.assertEqual(self._alert_kinds(), ["sync_failed"])
        detail = self.alerts.raise_alert.await_args.kwargs["detail"]
        self.assertIn("manual full resync failed", detail)
        self.assertNotIn("trigger a manual", detail)

    async def test_gmail_5xx_asks_pubsub_to_retry(self):
        self.gmail.list_history.side_effect = GmailUnavailableError("503")
        outcome = await self.service.handle_push(self.session, "purrf@example.com", 120)
        self.assertEqual(outcome, PushOutcome.RETRY)
        self.assertIsNotNone(self.state.last_error)
        self.assertEqual(self.state.last_history_id, 100)
        self.alerts.raise_alert.assert_not_awaited()
        self.session.commit.assert_awaited()

    async def test_rate_limit_asks_pubsub_to_retry(self):
        self.gmail.list_history.side_effect = RateLimitedError("429")
        outcome = await self.service.handle_push(self.session, "purrf@example.com", 120)
        self.assertEqual(outcome, PushOutcome.RETRY)

    async def test_auth_failure_alerts_and_acks(self):
        self.gmail.list_history.side_effect = RuntimeError("refresh token rejected")
        outcome = await self.service.handle_push(self.session, "purrf@example.com", 120)
        self.assertEqual(outcome, PushOutcome.ACK)
        self.assertEqual(self._alert_kinds(), ["sync_failed"])
        self.assertIn("refresh token rejected", self.state.last_error)
        self.session.commit.assert_awaited()

    async def test_push_lets_a_transport_error_propagate(self):
        self.gmail.list_history.side_effect = ConnectionError("reset")
        with self.assertRaises(ConnectionError):
            await self.service.handle_push(self.session, "purrf@example.com", 120)

    async def test_catch_up_does_not_touch_last_push_at(self):
        sentinel = object()
        self.state.last_push_at = sentinel
        self._three_threads()
        summary = await self.service.catch_up(self.session)
        self.gmail.list_history.assert_called_once_with(100)
        self.assertEqual(summary, {"threads": 1, "newMessages": 1, "failed": 0, "unrouted": []})
        self.assertIs(self.state.last_push_at, sentinel)

    async def test_catch_up_reraises_gmail_errors_after_recording(self):
        self.gmail.list_history.side_effect = GmailUnavailableError("503")
        with self.assertRaises(GmailUnavailableError):
            await self.service.catch_up(self.session)
        self.assertIsNotNone(self.state.last_error)
        self.assertEqual(self._alert_kinds(), ["sync_failed"])
        self.session.commit.assert_awaited()

    async def test_catch_up_counts_a_failing_thread_and_keeps_the_error(self):
        t1, t2 = self._tracked("t1"), self._tracked("t2")
        self._history({"t1": t1, "t2": t2})
        self.state.last_error = "earlier failure"

        async def sync(session, thread):
            if thread is t1:
                raise GmailNotFoundError("thread deleted")
            return 2

        self.handler.sync_tracked_thread.side_effect = sync
        summary = await self.service.catch_up(self.session)
        self.assertEqual(summary, {"threads": 1, "newMessages": 2, "failed": 1, "unrouted": []})
        self.assertEqual(self.state.last_error, "earlier failure")
        self.assertEqual(self.state.last_history_id, 150)
        self.alerts.raise_alert.assert_not_awaited()

    def _failing_threads(self, error, *failing_ids, ok_id="ok"):
        threads = {gid: self._tracked(gid) for gid in (*failing_ids, ok_id)}
        self._history(threads)

        async def sync(session, thread):
            if thread.gmail_thread_id in failing_ids:
                raise error
            return 1

        self.handler.sync_tracked_thread.side_effect = sync

    async def test_push_alerts_on_a_transient_thread_failure_naming_the_thread(self):
        self._failing_threads(RateLimitedError("429"), "t-rate")
        outcome = await self.service.handle_push(self.session, "purrf@example.com", 120)
        self.assertEqual(outcome, PushOutcome.ACK)
        self.assertEqual(self._alert_kinds(), ["sync_failed"])
        detail = self.alerts.raise_alert.await_args.kwargs["detail"]
        self.assertIn("t-rate", detail)
        self.assertIn("manual full resync", detail)
        self.assertIn("t-rate", self.state.last_error)
        self.assertEqual(self.state.last_history_id, 150)
        self.session.commit.assert_awaited()

    async def test_catch_up_alerts_on_a_transient_thread_failure(self):
        self._failing_threads(GmailUnavailableError("503"), "t-5xx")
        summary = await self.service.catch_up(self.session)
        self.assertEqual(summary, {"threads": 1, "newMessages": 1, "failed": 1, "unrouted": []})
        self.assertEqual(self._alert_kinds(), ["sync_failed"])
        self.assertIn("t-5xx", self.alerts.raise_alert.await_args.kwargs["detail"])

    async def test_push_does_not_alert_on_a_deleted_thread(self):
        self._failing_threads(GmailNotFoundError("404"), "t-gone")
        await self.service.handle_push(self.session, "purrf@example.com", 120)
        self.alerts.raise_alert.assert_not_awaited()
        self.assertIsNone(self.state.last_error)

    async def test_transient_failure_alert_truncates_a_long_thread_list(self):
        ids = [f"t{i:02d}" for i in range(12)]
        self._failing_threads(RuntimeError("boom"), *ids)
        await self.service.handle_push(self.session, "purrf@example.com", 120)
        detail = self.alerts.raise_alert.await_args.kwargs["detail"]
        self.assertIn("t09", detail)
        self.assertNotIn("t10", detail)
        self.assertIn("2 more", detail)

    async def test_catch_up_alerts_and_reraises_on_rate_limit(self):
        self.gmail.list_history.side_effect = RateLimitedError("429")
        with self.assertRaises(RateLimitedError):
            await self.service.catch_up(self.session)
        self.assertIsNotNone(self.state.last_error)
        self.assertEqual(self._alert_kinds(), ["sync_failed"])

    async def test_catch_up_alerts_and_reraises_on_a_transport_error(self):
        self.gmail.list_history.side_effect = ConnectionError("reset")
        with self.assertRaises(ConnectionError):
            await self.service.catch_up(self.session)
        self.assertIn("reset", self.state.last_error)
        self.assertEqual(self._alert_kinds(), ["sync_failed"])
        self.session.commit.assert_awaited()

    async def test_catch_up_on_an_expired_cursor_runs_the_full_resync(self):
        sentinel = object()
        self.state.last_push_at = sentinel
        self.gmail.list_history.side_effect = HistoryExpiredError("gone")
        self.handler.resync_all.return_value = {"scanned": 4}
        summary = await self.service.catch_up(self.session)
        self.assertEqual(
            summary,
            {
                "threads": 0,
                "newMessages": 0,
                "failed": 0,
                "unrouted": [],
                "fullResync": [{"scanned": 4}],
            },
        )
        self.assertIs(self.state.last_push_at, sentinel)
        self.assertEqual(self.state.last_history_id, 500)

    async def test_catch_up_without_topic_is_skipped(self):
        self.service = self._service(None)
        summary = await self.service.catch_up(self.session)
        self.assertEqual(summary, {"skipped": "GMAIL_WATCH_TOPIC is not set"})
        self.gmail.get_profile.assert_not_called()
        self.gmail.list_history.assert_not_called()

    async def test_renew_watch_stores_expiration(self):
        expiration = datetime(2026, 10, 7, tzinfo=timezone.utc)
        self.gmail.watch.return_value = {"history_id": 777, "expiration": expiration}
        summary = await self.service.renew_watch(self.session)
        self.gmail.watch.assert_called_once_with("projects/p/topics/gmail")
        self.assertEqual(self.state.watch_expiration, expiration)
        self.assertIsInstance(self.state.last_renewed_at, datetime)
        self.assertEqual(summary, {"expiration": expiration.isoformat()})
        self.session.commit.assert_awaited()

    async def test_renew_watch_creates_the_row_from_the_watch_history_id(self):
        self.states.get_for_update.return_value = None
        self.states.create.return_value = self.state
        self.gmail.watch.return_value = {
            "history_id": 777,
            "expiration": datetime(2026, 10, 7, tzinfo=timezone.utc),
        }
        await self.service.renew_watch(self.session)
        self.states.create.assert_awaited_once_with(
            self.session, "purrf@example.com", 777
        )

    async def test_renew_watch_sets_a_missing_cursor_and_clears_the_error(self):
        self.state.last_history_id = None
        self.state.last_error = "Forbidden: earlier renewal"
        self.gmail.watch.return_value = {
            "history_id": 777,
            "expiration": datetime(2026, 10, 7, tzinfo=timezone.utc),
        }
        await self.service.renew_watch(self.session)
        self.assertEqual(self.state.last_history_id, 777)
        self.assertIsNone(self.state.last_error)

    async def test_renew_watch_keeps_an_existing_cursor(self):
        self.gmail.watch.return_value = {
            "history_id": 777,
            "expiration": datetime(2026, 10, 7, tzinfo=timezone.utc),
        }
        await self.service.renew_watch(self.session)
        self.assertEqual(self.state.last_history_id, 100)

    async def test_renew_watch_failure_alerts_and_reraises(self):
        self.gmail.watch.side_effect = RuntimeError("forbidden")
        with self.assertRaises(RuntimeError):
            await self.service.renew_watch(self.session)
        self.assertEqual(self._alert_kinds(), ["watch_renewal_failed"])
        self.assertIsNotNone(self.state.last_error)
        self.session.commit.assert_awaited()

    async def test_renew_watch_failure_without_a_row_creates_one_to_alert_on(self):
        self.states.get_for_update.return_value = None
        created = Mock(id=4, last_error=None)
        self.states.create.return_value = created
        self.gmail.watch.side_effect = RuntimeError("forbidden")
        with self.assertRaises(RuntimeError):
            await self.service.renew_watch(self.session)
        self.states.create.assert_awaited_once_with(
            self.session, "purrf@example.com", None
        )
        self.assertIn("forbidden", created.last_error)
        self.assertIs(self.alerts.raise_alert.await_args.kwargs["state"], created)
        self.session.commit.assert_awaited()

    async def test_renew_watch_without_topic_is_skipped(self):
        self.service = self._service(None)
        summary = await self.service.renew_watch(self.session)
        self.assertEqual(summary, {"skipped": "GMAIL_WATCH_TOPIC is not set"})
        self.gmail.watch.assert_not_called()
        self.gmail.get_profile.assert_not_called()

    def _profile_lookup_fails(self):
        self.gmail.get_profile.side_effect = RuntimeError("refresh token revoked")
        self.states.get_single.return_value = self.state

    async def _assert_profile_failure_alerted(self, kind):
        self.assertEqual(self._alert_kinds(), [kind])
        self.assertIs(self.alerts.raise_alert.await_args.kwargs["state"], self.state)
        self.assertIn(
            "refresh token revoked", self.alerts.raise_alert.await_args.kwargs["detail"]
        )
        self.assertIn("refresh token revoked", self.state.last_error)
        self.states.get_single.assert_awaited_once_with(self.session)
        self.session.commit.assert_awaited()

    async def test_push_alerts_on_the_only_row_when_the_mailbox_lookup_fails(self):
        self._profile_lookup_fails()
        with self.assertRaises(RuntimeError):
            await self.service.handle_push(self.session, "purrf@example.com", 120)
        await self._assert_profile_failure_alerted("sync_failed")

    async def test_catch_up_alerts_on_the_only_row_when_the_mailbox_lookup_fails(self):
        self._profile_lookup_fails()
        with self.assertRaises(RuntimeError):
            await self.service.catch_up(self.session)
        await self._assert_profile_failure_alerted("sync_failed")

    async def test_renew_watch_alerts_on_the_only_row_when_the_mailbox_lookup_fails(
        self,
    ):
        self._profile_lookup_fails()
        with self.assertRaises(RuntimeError):
            await self.service.renew_watch(self.session)
        await self._assert_profile_failure_alerted("watch_renewal_failed")
        self.gmail.watch.assert_not_called()

    async def test_mailbox_lookup_failure_without_a_row_only_logs(self):
        self.gmail.get_profile.side_effect = RuntimeError("refresh token revoked")
        self.states.get_single.return_value = None
        with self.assertRaises(RuntimeError):
            await self.service.handle_push(self.session, "purrf@example.com", 120)
        self.alerts.raise_alert.assert_not_awaited()
        self.logger.error.assert_called()

    async def test_mailbox_address_is_fetched_once(self):
        await self.service.mailbox_address()
        self.assertEqual(await self.service.mailbox_address(), "purrf@example.com")
        self.gmail.get_profile.assert_called_once()


if __name__ == "__main__":
    unittest.main()
