import json
import os
from unittest import TestCase, main
from unittest.mock import MagicMock, patch

from backend.common.constants import EXPIRATION_REMINDER_EVENT
from backend.consumers.pubsub_sync_pull_service import PubSubSyncPullService

PROJECT_ID = "test-project"
MICROSOFT_SUB = "ms-sub"
GOOGLE_CHAT_SUB = "gc-sub"
GERRIT_SUB = "gerrit-sub"


class TestPubSubSyncPullService(TestCase):
    def setUp(self):
        self.mock_logger = MagicMock()
        self.mock_subscriber = MagicMock()
        self.mock_ms_util = MagicMock()
        self.mock_google_chat = MagicMock()
        self.mock_gerrit = MagicMock()
        self.mock_loop_mgr = MagicMock()
        self.service = PubSubSyncPullService(
            logger=self.mock_logger,
            subscriber_client=self.mock_subscriber,
            microsoft_chat_message_util=self.mock_ms_util,
            google_chat_processor_service=self.mock_google_chat,
            gerrit_processor_service=self.mock_gerrit,
            asyncio_event_loop_manager=self.mock_loop_mgr,
        )

    def _make_received(
        self, data_bytes, attributes=None, ack_id="ack-1", message_id="msg-1"
    ):
        msg = MagicMock()
        msg.data = data_bytes
        msg.attributes = attributes or {}
        msg.message_id = message_id
        received = MagicMock()
        received.message = msg
        received.ack_id = ack_id
        return received

    def _make_pull_response(self, received_messages):
        response = MagicMock()
        response.received_messages = received_messages
        return response

    def _pull_side_effect(self, *batches):
        """Return side_effect list: each batch followed by a terminal empty response."""
        responses = [self._make_pull_response(list(batch)) for batch in batches]
        responses.append(self._make_pull_response([]))
        return responses

    def test_pull_and_process_no_messages(self):
        self.mock_subscriber.pull.return_value = self._make_pull_response([])
        process_fn = MagicMock()

        result = self.service._pull_and_process(PROJECT_ID, "sub", process_fn)

        self.assertEqual(result, {"processed": 0, "failed": 0})
        process_fn.assert_not_called()
        self.mock_subscriber.acknowledge.assert_not_called()

    def test_pull_and_process_all_success(self):
        r1 = self._make_received(b"data1", {}, ack_id="ack-1", message_id="msg-1")
        r2 = self._make_received(b"data2", {}, ack_id="ack-2", message_id="msg-2")
        self.mock_subscriber.pull.side_effect = self._pull_side_effect([r1, r2])
        process_fn = MagicMock()

        result = self.service._pull_and_process(PROJECT_ID, "sub", process_fn)

        self.assertEqual(result, {"processed": 2, "failed": 0})
        self.assertEqual(process_fn.call_count, 2)
        self.mock_subscriber.acknowledge.assert_called_once()
        ack_ids = self.mock_subscriber.acknowledge.call_args.kwargs["ack_ids"]
        self.assertIn("ack-1", ack_ids)
        self.assertIn("ack-2", ack_ids)
        self.mock_subscriber.modify_ack_deadline.assert_not_called()

    def test_pull_and_process_all_failure(self):
        r1 = self._make_received(b"data", {}, ack_id="ack-1")
        self.mock_subscriber.pull.side_effect = self._pull_side_effect([r1])
        process_fn = MagicMock(side_effect=Exception("boom"))

        result = self.service._pull_and_process(PROJECT_ID, "sub", process_fn)

        self.assertEqual(result, {"processed": 0, "failed": 1})
        self.mock_subscriber.acknowledge.assert_not_called()
        self.mock_logger.error.assert_called_once()
        nack_ids = self.mock_subscriber.modify_ack_deadline.call_args.kwargs["ack_ids"]
        self.assertIn("ack-1", nack_ids)
        self.assertEqual(
            self.mock_subscriber.modify_ack_deadline.call_args.kwargs[
                "ack_deadline_seconds"
            ],
            0,
        )

    def test_pull_and_process_partial_failure(self):
        r1 = self._make_received(b"ok", {}, ack_id="ack-ok", message_id="msg-1")
        r2 = self._make_received(b"bad", {}, ack_id="ack-bad", message_id="msg-2")
        self.mock_subscriber.pull.side_effect = self._pull_side_effect([r1, r2])
        process_fn = MagicMock(side_effect=[None, Exception("fail")])

        result = self.service._pull_and_process(PROJECT_ID, "sub", process_fn)

        self.assertEqual(result, {"processed": 1, "failed": 1})
        ack_ids = self.mock_subscriber.acknowledge.call_args.kwargs["ack_ids"]
        self.assertIn("ack-ok", ack_ids)
        self.assertNotIn("ack-bad", ack_ids)
        nack_ids = self.mock_subscriber.modify_ack_deadline.call_args.kwargs["ack_ids"]
        self.assertIn("ack-bad", nack_ids)
        self.assertNotIn("ack-ok", nack_ids)

    def test_pull_and_process_loops_multiple_batches(self):
        r1 = self._make_received(b"data1", {}, ack_id="ack-1", message_id="msg-1")
        r2 = self._make_received(b"data2", {}, ack_id="ack-2", message_id="msg-2")
        self.mock_subscriber.pull.side_effect = self._pull_side_effect([r1], [r2])
        process_fn = MagicMock()

        result = self.service._pull_and_process(PROJECT_ID, "sub", process_fn)

        self.assertEqual(result, {"processed": 2, "failed": 0})
        self.assertEqual(self.mock_subscriber.pull.call_count, 3)
        self.assertEqual(self.mock_subscriber.acknowledge.call_count, 2)

    def test_pull_and_process_caps_at_deadline(self):
        # Always return one message so the loop never naturally drains.
        def make_msg():
            return self._make_received(b"data", {}, ack_id="ack")

        self.mock_subscriber.pull.side_effect = (
            lambda *a, **kw: self._make_pull_response([make_msg()])
        )
        process_fn = MagicMock()

        # First check returns 0 (start), subsequent checks exceed deadline.
        with patch(
            "backend.consumers.pubsub_sync_pull_service.time.monotonic",
            side_effect=[0, 0, 5000, 5000],
        ):
            result = self.service._pull_and_process(
                PROJECT_ID,
                "sub",
                process_fn,
                max_iterations=100,
                deadline_seconds=1,
            )

        # Loop ran exactly once before the deadline check fired.
        self.assertEqual(result["processed"], 1)
        warning_calls = [
            c
            for c in self.mock_logger.warning.call_args_list
            if "deadline" in c.args[0]
        ]
        self.assertEqual(len(warning_calls), 1)

    def test_pull_and_process_caps_at_max_iterations(self):
        # Always return one message so the loop never naturally drains.
        # Distinct message_ids so the dedup logic still counts each as
        # processed.
        counter = {"n": 0}

        def make_msg():
            counter["n"] += 1
            return self._make_received(
                b"data",
                {},
                ack_id=f"ack-{counter['n']}",
                message_id=f"msg-{counter['n']}",
            )

        self.mock_subscriber.pull.side_effect = (
            lambda *a, **kw: self._make_pull_response([make_msg()])
        )
        process_fn = MagicMock()

        result = self.service._pull_and_process(
            PROJECT_ID, "sub", process_fn, max_iterations=3
        )

        self.assertEqual(result, {"processed": 3, "failed": 0})
        self.assertEqual(self.mock_subscriber.pull.call_count, 3)
        # Hit-cap warning should have been logged.
        warning_calls = [
            c
            for c in self.mock_logger.warning.call_args_list
            if "max_iterations" in c.args[0]
        ]
        self.assertEqual(len(warning_calls), 1)

    def test_pull_and_process_uses_correct_subscription_path(self):
        self.mock_subscriber.subscription_path.return_value = (
            "projects/proj/subscriptions/sub"
        )
        self.mock_subscriber.pull.return_value = self._make_pull_response([])

        self.service._pull_and_process(PROJECT_ID, "sub", MagicMock())

        self.mock_subscriber.subscription_path.assert_called_once_with(
            PROJECT_ID, "sub"
        )
        self.mock_subscriber.pull.assert_called_once_with(
            subscription="projects/proj/subscriptions/sub",
            max_messages=10,
            timeout=60,
        )

    def test_sync_pull_microsoft_success(self):
        data = json.dumps({
            "changeType": "created",
            "resource": "chats/1/messages/2",
        }).encode()
        self.mock_subscriber.pull.side_effect = self._pull_side_effect([
            self._make_received(data, {})
        ])

        result = self.service.sync_pull_microsoft(PROJECT_ID, MICROSOFT_SUB)

        self.mock_ms_util.sync_near_real_time_message_to_redis.assert_called_once_with(
            "created", "chats/1/messages/2"
        )
        self.mock_loop_mgr.run_async_in_background_loop.assert_called_once()
        self.assertEqual(result, {"processed": 1, "failed": 0})

    def test_sync_pull_microsoft_loop_manager_error_causes_failed(self):
        data = json.dumps({"changeType": "updated", "resource": "res"}).encode()
        received = self._make_received(data, {}, ack_id="ack-ms")
        self.mock_subscriber.pull.side_effect = self._pull_side_effect([received])
        self.mock_loop_mgr.run_async_in_background_loop.side_effect = Exception(
            "loop error"
        )

        result = self.service.sync_pull_microsoft(PROJECT_ID, MICROSOFT_SUB)

        self.assertEqual(result, {"processed": 0, "failed": 1})
        self.mock_subscriber.acknowledge.assert_not_called()
        nack_ids = self.mock_subscriber.modify_ack_deadline.call_args.kwargs["ack_ids"]
        self.assertIn("ack-ms", nack_ids)

    def test_sync_pull_microsoft_passes_coroutine_to_loop_manager(self):
        data = json.dumps({"changeType": "deleted", "resource": "r"}).encode()
        self.mock_subscriber.pull.side_effect = self._pull_side_effect([
            self._make_received(data, {})
        ])
        sentinel_coroutine = MagicMock()
        self.mock_ms_util.sync_near_real_time_message_to_redis.return_value = (
            sentinel_coroutine
        )

        self.service.sync_pull_microsoft(PROJECT_ID, MICROSOFT_SUB)

        self.mock_loop_mgr.run_async_in_background_loop.assert_called_once_with(
            sentinel_coroutine, timeout=60
        )

    def test_sync_pull_google_chat_success(self):
        data = json.dumps({"type": "MESSAGE"}).encode()
        attributes = {"ce-type": EXPIRATION_REMINDER_EVENT, "attr": "val"}
        self.mock_subscriber.pull.side_effect = self._pull_side_effect([
            self._make_received(data, attributes)
        ])

        result = self.service.sync_pull_google_chat(PROJECT_ID, GOOGLE_CHAT_SUB)

        self.mock_google_chat.process_event.assert_called_once_with(
            {"type": "MESSAGE"}, attributes
        )
        self.assertEqual(result, {"processed": 1, "failed": 0})

    def test_sync_pull_google_chat_process_event_error(self):
        data = json.dumps({}).encode()
        received = self._make_received(
            data, {"ce-type": EXPIRATION_REMINDER_EVENT}, ack_id="ack-gc"
        )
        self.mock_subscriber.pull.side_effect = self._pull_side_effect([received])
        self.mock_google_chat.process_event.side_effect = Exception("gc error")

        result = self.service.sync_pull_google_chat(PROJECT_ID, GOOGLE_CHAT_SUB)

        self.assertEqual(result, {"processed": 0, "failed": 1})
        self.mock_subscriber.acknowledge.assert_not_called()
        nack_ids = self.mock_subscriber.modify_ack_deadline.call_args.kwargs["ack_ids"]
        self.assertIn("ack-gc", nack_ids)

    def test_sync_pull_gerrit_success(self):
        payload = {"type": "patchset-created", "change": {"id": "123"}}
        data = json.dumps(payload).encode()
        self.mock_subscriber.pull.side_effect = self._pull_side_effect([
            self._make_received(data, {})
        ])

        result = self.service.sync_pull_gerrit(PROJECT_ID, GERRIT_SUB)

        self.mock_gerrit.store_payload.assert_called_once_with(payload)
        self.assertEqual(result, {"processed": 1, "failed": 0})

    def test_sync_pull_gerrit_store_payload_error(self):
        data = json.dumps({}).encode()
        received = self._make_received(data, {}, ack_id="ack-gerrit")
        self.mock_subscriber.pull.side_effect = self._pull_side_effect([received])
        self.mock_gerrit.store_payload.side_effect = Exception("gerrit error")

        result = self.service.sync_pull_gerrit(PROJECT_ID, GERRIT_SUB)

        self.assertEqual(result, {"processed": 0, "failed": 1})
        self.mock_subscriber.acknowledge.assert_not_called()
        nack_ids = self.mock_subscriber.modify_ack_deadline.call_args.kwargs["ack_ids"]
        self.assertIn("ack-gerrit", nack_ids)

    @patch.dict(
        os.environ,
        {
            "PUBSUB_PROJECT_ID": PROJECT_ID,
            "MICROSOFT_SUBSCRIPTION_ID": MICROSOFT_SUB,
            "GOOGLE_CHAT_SUBSCRIPTION_ID": GOOGLE_CHAT_SUB,
            "GERRIT_SUBSCRIPTION_ID": GERRIT_SUB,
        },
    )
    def test_sync_pull_all_calls_all_subscriptions(self):
        self.mock_subscriber.pull.return_value = self._make_pull_response([])

        result = self.service.sync_pull_all()

        self.assertIn("microsoft", result)
        self.assertIn("google_chat", result)
        self.assertIn("gerrit", result)
        self.assertEqual(self.mock_subscriber.pull.call_count, 3)

    @patch.dict(
        os.environ,
        {
            "PUBSUB_PROJECT_ID": PROJECT_ID,
            "MICROSOFT_SUBSCRIPTION_ID": MICROSOFT_SUB,
        },
        clear=True,
    )
    def test_sync_pull_all_skips_missing_subscriptions(self):
        self.mock_subscriber.pull.return_value = self._make_pull_response([])

        result = self.service.sync_pull_all()

        self.assertIn("microsoft", result)
        self.assertNotIn("google_chat", result)
        self.assertNotIn("gerrit", result)
        self.assertEqual(self.mock_subscriber.pull.call_count, 1)

    @patch.dict(os.environ, {}, clear=True)
    def test_sync_pull_all_skips_all_when_no_project_id(self):
        result = self.service.sync_pull_all()

        self.assertEqual(result, {})
        self.mock_subscriber.pull.assert_not_called()

    @patch.dict(
        os.environ,
        {
            "PUBSUB_PROJECT_ID": PROJECT_ID,
            "MICROSOFT_SUBSCRIPTION_ID": MICROSOFT_SUB,
            "GOOGLE_CHAT_SUBSCRIPTION_ID": GOOGLE_CHAT_SUB,
            "GERRIT_SUBSCRIPTION_ID": GERRIT_SUB,
        },
    )
    def test_sync_pull_all_returns_combined_results(self):
        self.mock_subscriber.pull.return_value = self._make_pull_response([])

        result = self.service.sync_pull_all(max_messages=50)

        for key in ("microsoft", "google_chat", "gerrit"):
            self.assertIn("processed", result[key])
            self.assertIn("failed", result[key])

    @patch.dict(
        os.environ,
        {
            "PUBSUB_PROJECT_ID": PROJECT_ID,
            "MICROSOFT_SUBSCRIPTION_ID": MICROSOFT_SUB,
            "GOOGLE_CHAT_SUBSCRIPTION_ID": GOOGLE_CHAT_SUB,
            "GERRIT_SUBSCRIPTION_ID": GERRIT_SUB,
        },
    )
    def test_sync_pull_all_isolates_subscription_failures(self):
        # Simulate microsoft sync raising before _pull_and_process catches it
        # (e.g. setup-time exception). google_chat and gerrit must still run.
        with patch.object(
            self.service,
            "sync_pull_microsoft",
            side_effect=RuntimeError("ms setup failed"),
        ):
            self.mock_subscriber.pull.return_value = self._make_pull_response([])
            result = self.service.sync_pull_all()

        self.assertEqual(result["microsoft"], {"processed": 0, "failed": 0})
        self.assertEqual(result["google_chat"], {"processed": 0, "failed": 0})
        self.assertEqual(result["gerrit"], {"processed": 0, "failed": 0})
        self.mock_logger.error.assert_called()

    @patch.dict(
        os.environ,
        {
            "PUBSUB_PROJECT_ID": PROJECT_ID,
            "MICROSOFT_SUBSCRIPTION_ID": MICROSOFT_SUB,
            "GOOGLE_CHAT_SUBSCRIPTION_ID": GOOGLE_CHAT_SUB,
            "GERRIT_SUBSCRIPTION_ID": GERRIT_SUB,
        },
    )
    def test_sync_pull_all_isolates_middle_subscription(self):
        with patch.object(
            self.service,
            "sync_pull_google_chat",
            side_effect=RuntimeError("gc broke"),
        ):
            self.mock_subscriber.pull.return_value = self._make_pull_response([])
            result = self.service.sync_pull_all()

        self.assertEqual(result["microsoft"], {"processed": 0, "failed": 0})
        self.assertEqual(result["google_chat"], {"processed": 0, "failed": 0})
        self.assertEqual(result["gerrit"], {"processed": 0, "failed": 0})

    @patch.dict(
        os.environ,
        {
            "PUBSUB_PROJECT_ID": PROJECT_ID,
            "MICROSOFT_SUBSCRIPTION_ID": MICROSOFT_SUB,
            "GOOGLE_CHAT_SUBSCRIPTION_ID": GOOGLE_CHAT_SUB,
            "GERRIT_SUBSCRIPTION_ID": GERRIT_SUB,
        },
    )
    def test_sync_pull_all_isolates_last_subscription(self):
        with patch.object(
            self.service,
            "sync_pull_gerrit",
            side_effect=RuntimeError("gerrit broke"),
        ):
            self.mock_subscriber.pull.return_value = self._make_pull_response([])
            result = self.service.sync_pull_all()

        self.assertEqual(result["microsoft"], {"processed": 0, "failed": 0})
        self.assertEqual(result["google_chat"], {"processed": 0, "failed": 0})
        self.assertEqual(result["gerrit"], {"processed": 0, "failed": 0})

    def test_sync_pull_google_chat_acks_unsupported_event(self):
        # Unsupported events must NOT be nacked — that would cause a redelivery
        # storm in the sync loop. The wrapper pre-filters and acks.
        data = json.dumps({}).encode()
        received = self._make_received(data, {"ce-type": "junk.event"}, ack_id="ack-x")
        self.mock_subscriber.pull.side_effect = self._pull_side_effect([received])

        result = self.service.sync_pull_google_chat(PROJECT_ID, GOOGLE_CHAT_SUB)

        self.assertEqual(result, {"processed": 1, "failed": 0})
        # process_event was never invoked — pre-filter dropped it.
        self.mock_google_chat.process_event.assert_not_called()
        ack_ids = self.mock_subscriber.acknowledge.call_args.kwargs["ack_ids"]
        self.assertIn("ack-x", ack_ids)
        self.mock_subscriber.modify_ack_deadline.assert_not_called()

    def test_pull_and_process_pull_exception_breaks_loop(self):
        self.mock_subscriber.pull.side_effect = Exception("network error")
        process_fn = MagicMock()

        result = self.service._pull_and_process(PROJECT_ID, "sub", process_fn)

        self.assertEqual(result, {"processed": 0, "failed": 0})
        process_fn.assert_not_called()
        self.mock_subscriber.acknowledge.assert_not_called()
        self.mock_logger.error.assert_called_once()

    def test_pull_and_process_pull_exception_logs_subscription_info(self):
        self.mock_subscriber.pull.side_effect = Exception("rpc error")

        self.service._pull_and_process(PROJECT_ID, "sub-id", MagicMock())

        log_args = self.mock_logger.error.call_args.args
        self.assertIn(PROJECT_ID, log_args)
        self.assertIn("sub-id", log_args)

    def test_pull_and_process_failure_log_includes_subscription_info(self):
        r1 = self._make_received(b"data", {}, message_id="msg-x")
        self.mock_subscriber.pull.side_effect = self._pull_side_effect([r1])
        process_fn = MagicMock(side_effect=Exception("boom"))

        self.service._pull_and_process(PROJECT_ID, "sub-id", process_fn)

        log_args = self.mock_logger.error.call_args.args
        self.assertIn(PROJECT_ID, log_args)
        self.assertIn("sub-id", log_args)
        self.assertIn("msg-x", log_args)

    def test_pull_and_process_custom_max_messages(self):
        self.mock_subscriber.pull.return_value = self._make_pull_response([])

        self.service._pull_and_process(PROJECT_ID, "sub", MagicMock(), max_messages=50)

        self.mock_subscriber.pull.assert_called_once_with(
            subscription=self.mock_subscriber.subscription_path.return_value,
            max_messages=50,
            timeout=60,
        )

    def test_pull_and_process_counts_accumulate_across_batches(self):
        good = self._make_received(b"ok", {}, ack_id="ack-ok", message_id="msg-ok")
        bad = self._make_received(b"bad", {}, ack_id="ack-bad", message_id="msg-bad")
        self.mock_subscriber.pull.side_effect = self._pull_side_effect([good], [bad])
        process_fn = MagicMock(side_effect=[None, Exception("fail")])

        result = self.service._pull_and_process(PROJECT_ID, "sub", process_fn)

        self.assertEqual(result, {"processed": 1, "failed": 1})

    def test_sync_pull_microsoft_timeout_causes_failed_and_nack(self):
        data = json.dumps({"changeType": "created", "resource": "r"}).encode()
        received = self._make_received(data, {}, ack_id="ack-timeout")
        self.mock_subscriber.pull.side_effect = self._pull_side_effect([received])
        self.mock_loop_mgr.run_async_in_background_loop.side_effect = TimeoutError()

        result = self.service.sync_pull_microsoft(PROJECT_ID, MICROSOFT_SUB)

        self.assertEqual(result, {"processed": 0, "failed": 1})
        self.mock_subscriber.acknowledge.assert_not_called()
        nack_ids = self.mock_subscriber.modify_ack_deadline.call_args.kwargs["ack_ids"]
        self.assertIn("ack-timeout", nack_ids)

    def test_sync_pull_microsoft_malformed_json_causes_failed_and_nack(self):
        received = self._make_received(b"not-json", {}, ack_id="ack-bad-json")
        self.mock_subscriber.pull.side_effect = self._pull_side_effect([received])

        result = self.service.sync_pull_microsoft(PROJECT_ID, MICROSOFT_SUB)

        self.assertEqual(result, {"processed": 0, "failed": 1})
        self.mock_subscriber.acknowledge.assert_not_called()
        nack_ids = self.mock_subscriber.modify_ack_deadline.call_args.kwargs["ack_ids"]
        self.assertIn("ack-bad-json", nack_ids)

    def test_sync_pull_google_chat_malformed_json_causes_failed_and_nack(self):
        received = self._make_received(
            b"not-json",
            {"ce-type": EXPIRATION_REMINDER_EVENT},
            ack_id="ack-bad-json",
        )
        self.mock_subscriber.pull.side_effect = self._pull_side_effect([received])

        result = self.service.sync_pull_google_chat(PROJECT_ID, GOOGLE_CHAT_SUB)

        self.assertEqual(result, {"processed": 0, "failed": 1})
        self.mock_subscriber.acknowledge.assert_not_called()
        nack_ids = self.mock_subscriber.modify_ack_deadline.call_args.kwargs["ack_ids"]
        self.assertIn("ack-bad-json", nack_ids)

    def test_sync_pull_gerrit_malformed_json_causes_failed_and_nack(self):
        received = self._make_received(b"not-json", {}, ack_id="ack-bad-json")
        self.mock_subscriber.pull.side_effect = self._pull_side_effect([received])

        result = self.service.sync_pull_gerrit(PROJECT_ID, GERRIT_SUB)

        self.assertEqual(result, {"processed": 0, "failed": 1})
        self.mock_subscriber.acknowledge.assert_not_called()
        nack_ids = self.mock_subscriber.modify_ack_deadline.call_args.kwargs["ack_ids"]
        self.assertIn("ack-bad-json", nack_ids)


if __name__ == "__main__":
    main()
