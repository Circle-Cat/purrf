import base64
import json
import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from backend.common.constants import (
    ALL_GOOGLE_CHAT_EVENT_TYPES,
    EXPIRATION_REMINDER_EVENT,
)
from backend.internal_activity_service.activity_query_cache import (
    ActivityQueryCache,
    GERRIT_STATS_QUERY,
    GOOGLE_CHAT_COUNT_QUERY,
    MICROSOFT_CHAT_COUNT_QUERY,
    SUMMARY_QUERY,
)
from backend.consumers.pubsub_push_service import (
    PubSubPushOutcome,
    PubSubPushService,
)

_BEARER = "Bearer push-token"
_CHAT_EVENT = ALL_GOOGLE_CHAT_EVENT_TYPES[0]


def _envelope(payload, attributes=None):
    data = base64.b64encode(json.dumps(payload).encode()).decode()
    message = {"data": data, "messageId": "m-1"}
    if attributes is not None:
        message["attributes"] = attributes
    return {"message": message, "subscription": "s"}


class PubSubPushServiceTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.auth_service = MagicMock()
        self.auth_service.verify_google_token.return_value = {"sub": "111-pusher"}
        self.chat_processor = MagicMock()
        self.gerrit_processor = MagicMock()
        self.microsoft_util = AsyncMock()
        self.logger = MagicMock()
        self.activity_query_cache = MagicMock()
        self.service = self._service(frozenset({"111-pusher"}))

    def _service(self, pusher_subs):
        return PubSubPushService(
            logger=self.logger,
            auth_service=self.auth_service,
            pusher_subs=pusher_subs,
            google_chat_processor_service=self.chat_processor,
            gerrit_processor_service=self.gerrit_processor,
            microsoft_chat_message_util=self.microsoft_util,
            activity_query_cache=self.activity_query_cache,
        )

    def _assert_nothing_processed(self):
        self.chat_processor.process_event.assert_not_called()
        self.gerrit_processor.store_payload.assert_not_called()
        self.microsoft_util.sync_near_real_time_message_to_redis.assert_not_awaited()

    async def test_missing_bearer_is_refused(self):
        outcome = await self.service.receive_google_chat("", _envelope({}))

        self.assertEqual(outcome, PubSubPushOutcome.REFUSED)
        self.auth_service.verify_google_token.assert_not_called()
        self._assert_nothing_processed()

    async def test_unverifiable_token_is_refused(self):
        self.auth_service.verify_google_token.side_effect = ValueError("expired")

        outcome = await self.service.receive_gerrit(_BEARER, _envelope({}))

        self.assertEqual(outcome, PubSubPushOutcome.REFUSED)
        self._assert_nothing_processed()

    async def test_unknown_sub_is_refused(self):
        self.auth_service.verify_google_token.return_value = {"sub": "other"}

        outcome = await self.service.receive_google_chat(_BEARER, _envelope({}))

        self.assertEqual(outcome, PubSubPushOutcome.REFUSED)
        self._assert_nothing_processed()

    async def test_empty_allowlist_refuses_everyone(self):
        service = self._service(frozenset())

        outcome = await service.receive_gerrit(_BEARER, _envelope({}))

        self.assertEqual(outcome, PubSubPushOutcome.REFUSED)
        self._assert_nothing_processed()

    async def test_the_token_is_verified_without_its_scheme(self):
        await self.service.receive_gerrit(_BEARER, _envelope({}))

        self.auth_service.verify_google_token.assert_called_once_with("push-token")

    async def test_google_chat_event_is_processed_with_data_and_attributes(self):
        payload = {"message": {"name": "spaces/a/messages/b"}}
        attributes = {"ce-type": _CHAT_EVENT, "ce-id": "event-7"}

        outcome = await self.service.receive_google_chat(
            _BEARER, _envelope(payload, attributes)
        )

        self.assertEqual(outcome, PubSubPushOutcome.ACK)
        self.chat_processor.process_event.assert_called_once_with(payload, attributes)
        self.gerrit_processor.store_payload.assert_not_called()

    async def test_expiration_reminder_reaches_the_processor(self):
        payload = {"subscription": {"name": "subscriptions/x"}}
        attributes = {"ce-type": EXPIRATION_REMINDER_EVENT}

        outcome = await self.service.receive_google_chat(
            _BEARER, _envelope(payload, attributes)
        )

        self.assertEqual(outcome, PubSubPushOutcome.ACK)
        self.chat_processor.process_event.assert_called_once_with(payload, attributes)

    async def test_unsupported_google_chat_event_is_acked_unprocessed(self):
        outcome = await self.service.receive_google_chat(
            _BEARER,
            _envelope({}, {"ce-type": "google.workspace.chat.reaction.v1.created"}),
        )

        self.assertEqual(outcome, PubSubPushOutcome.ACK)
        self.chat_processor.process_event.assert_not_called()

    async def test_google_chat_message_without_attributes_is_acked_unprocessed(self):
        outcome = await self.service.receive_google_chat(_BEARER, _envelope({}))

        self.assertEqual(outcome, PubSubPushOutcome.ACK)
        self.chat_processor.process_event.assert_not_called()

    async def test_google_chat_processing_failure_is_retried(self):
        self.chat_processor.process_event.side_effect = ValueError("no sender")

        outcome = await self.service.receive_google_chat(
            _BEARER, _envelope({}, {"ce-type": _CHAT_EVENT})
        )

        self.assertEqual(outcome, PubSubPushOutcome.RETRY)

    async def test_microsoft_chat_change_is_synced_by_type_and_resource(self):
        payload = {
            "changeType": "updated",
            "resource": "chats('19:abc')/messages('1700')",
            "subscriptionId": "sub-9",
        }

        outcome = await self.service.receive_microsoft_chat(_BEARER, _envelope(payload))

        self.assertEqual(outcome, PubSubPushOutcome.ACK)
        self.microsoft_util.sync_near_real_time_message_to_redis.assert_awaited_once_with(
            "updated", "chats('19:abc')/messages('1700')"
        )
        self.chat_processor.process_event.assert_not_called()
        self.gerrit_processor.store_payload.assert_not_called()

    async def test_microsoft_chat_failure_is_retried(self):
        self.microsoft_util.sync_near_real_time_message_to_redis.side_effect = (
            ValueError("Unsupported change type")
        )

        outcome = await self.service.receive_microsoft_chat(
            _BEARER, _envelope({"changeType": "moved", "resource": "r"})
        )

        self.assertEqual(outcome, PubSubPushOutcome.RETRY)

    async def test_microsoft_chat_caller_is_checked_too(self):
        self.auth_service.verify_google_token.return_value = {"sub": "other"}

        outcome = await self.service.receive_microsoft_chat(
            _BEARER, _envelope({"changeType": "created", "resource": "r"})
        )

        self.assertEqual(outcome, PubSubPushOutcome.REFUSED)
        self._assert_nothing_processed()

    async def test_gerrit_event_is_stored(self):
        payload = {"type": "comment-added", "change": {"number": 42}}

        outcome = await self.service.receive_gerrit(
            _BEARER, _envelope(payload, {"origin": "gerrit"})
        )

        self.assertEqual(outcome, PubSubPushOutcome.ACK)
        self.gerrit_processor.store_payload.assert_called_once_with(payload)
        self.chat_processor.process_event.assert_not_called()

    async def test_gerrit_processing_failure_is_retried(self):
        self.gerrit_processor.store_payload.side_effect = RuntimeError("redis down")

        outcome = await self.service.receive_gerrit(_BEARER, _envelope({"type": "x"}))

        self.assertEqual(outcome, PubSubPushOutcome.RETRY)

    async def test_unreadable_envelopes_are_retried_unprocessed(self):
        not_json = base64.b64encode(b"not json").decode()
        for envelope in (
            None,
            {},
            {"message": {}},
            {"message": {"data": "%%%"}},
            {"message": {"data": not_json}},
        ):
            with self.subTest(envelope=envelope):
                for receive in (
                    self.service.receive_google_chat,
                    self.service.receive_microsoft_chat,
                    self.service.receive_gerrit,
                ):
                    outcome = await receive(_BEARER, envelope)

                    self.assertEqual(outcome, PubSubPushOutcome.RETRY)
        self._assert_nothing_processed()

    async def test_applied_chat_pushes_drop_todays_cached_results_of_their_source(self):
        cases = [
            (
                self.service.receive_google_chat,
                _envelope({}, {"ce-type": _CHAT_EVENT}),
                {GOOGLE_CHAT_COUNT_QUERY, SUMMARY_QUERY},
            ),
            (
                self.service.receive_microsoft_chat,
                _envelope({"changeType": "created", "resource": "r"}),
                {MICROSOFT_CHAT_COUNT_QUERY, SUMMARY_QUERY},
            ),
        ]
        for receive, envelope, methods in cases:
            with self.subTest(receive=receive.__name__):
                self.activity_query_cache.reset_mock()

                outcome = await receive(_BEARER, envelope)

                self.assertEqual(outcome, PubSubPushOutcome.ACK)
                self.activity_query_cache.clear_current.assert_called_once_with(methods)
                self.activity_query_cache.clear_methods.assert_not_called()

    async def test_applied_gerrit_push_drops_every_cached_gerrit_and_summary_result(
        self,
    ):
        outcome = await self.service.receive_gerrit(
            _BEARER, _envelope({"type": "change-merged"})
        )

        self.assertEqual(outcome, PubSubPushOutcome.ACK)
        self.activity_query_cache.clear_methods.assert_called_once_with({
            GERRIT_STATS_QUERY,
            SUMMARY_QUERY,
        })
        self.activity_query_cache.clear_current.assert_not_called()

    async def test_gerrit_push_drops_past_ranges_but_chat_push_keeps_them(self):
        # A Gerrit push rewrites this week's bucket, which a range that ended
        # yesterday also reads; a chat push only adds today's messages.
        now = datetime(2026, 10, 17, 15, 0, tzinfo=timezone.utc)
        yesterday_end = datetime(2026, 10, 16, 23, 59, 59, tzinfo=timezone.utc)
        today_end = datetime(2026, 10, 17, 23, 59, 59, tzinfo=timezone.utc)
        self.activity_query_cache = ActivityQueryCache(
            logger=MagicMock(), clock=lambda: now
        )
        service = self._service(frozenset({"111-pusher"}))
        cache = self.activity_query_cache
        for method in (GERRIT_STATS_QUERY, SUMMARY_QUERY, GOOGLE_CHAT_COUNT_QUERY):
            cache.get_or_compute(method, ("past",), yesterday_end, lambda: "old")
            cache.get_or_compute(method, ("today",), today_end, lambda: "old")

        await service.receive_google_chat(
            _BEARER, _envelope({}, {"ce-type": _CHAT_EVENT})
        )
        self.assertEqual(
            cache.get_or_compute(
                SUMMARY_QUERY, ("past",), yesterday_end, lambda: "new"
            ),
            "old",
        )
        self.assertEqual(
            cache.get_or_compute(
                GERRIT_STATS_QUERY, ("past",), yesterday_end, lambda: "new"
            ),
            "old",
        )

        await service.receive_gerrit(_BEARER, _envelope({"type": "change-merged"}))

        for method in (GERRIT_STATS_QUERY, SUMMARY_QUERY):
            with self.subTest(method=method):
                self.assertEqual(
                    cache.get_or_compute(
                        method, ("past",), yesterday_end, lambda: "new"
                    ),
                    "new",
                )
        self.assertEqual(
            cache.get_or_compute(
                GOOGLE_CHAT_COUNT_QUERY, ("past",), yesterday_end, lambda: "new"
            ),
            "old",
        )

    async def test_pushes_that_wrote_nothing_leave_the_cache_alone(self):
        cases = {
            "expiration reminder": self.service.receive_google_chat(
                _BEARER,
                _envelope(
                    {"subscription": {"name": "subscriptions/x"}},
                    {"ce-type": EXPIRATION_REMINDER_EVENT},
                ),
            ),
            "unsupported chat event": self.service.receive_google_chat(
                _BEARER,
                _envelope({}, {"ce-type": "google.workspace.chat.reaction.v1.created"}),
            ),
            "unreadable envelope": self.service.receive_gerrit(_BEARER, None),
            "refused caller": self.service.receive_gerrit("", _envelope({})),
        }
        for name, push in cases.items():
            with self.subTest(case=name):
                await push

        self.activity_query_cache.clear_current.assert_not_called()
        self.activity_query_cache.clear_methods.assert_not_called()

    async def test_failed_pushes_leave_the_cache_alone(self):
        self.chat_processor.process_event.side_effect = ValueError("no sender")
        self.gerrit_processor.store_payload.side_effect = RuntimeError("redis down")
        self.microsoft_util.sync_near_real_time_message_to_redis.side_effect = (
            ValueError("Unsupported change type")
        )

        outcomes = [
            await self.service.receive_google_chat(
                _BEARER, _envelope({}, {"ce-type": _CHAT_EVENT})
            ),
            await self.service.receive_microsoft_chat(
                _BEARER, _envelope({"changeType": "moved", "resource": "r"})
            ),
            await self.service.receive_gerrit(_BEARER, _envelope({"type": "x"})),
        ]

        self.assertEqual(outcomes, [PubSubPushOutcome.RETRY] * 3)
        self.activity_query_cache.clear_current.assert_not_called()
        self.activity_query_cache.clear_methods.assert_not_called()


if __name__ == "__main__":
    unittest.main()
