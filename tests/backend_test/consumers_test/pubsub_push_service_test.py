import base64
import json
import unittest
from unittest.mock import MagicMock

from backend.common.constants import (
    ALL_GOOGLE_CHAT_EVENT_TYPES,
    EXPIRATION_REMINDER_EVENT,
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
        self.logger = MagicMock()
        self.service = self._service(frozenset({"111-pusher"}))

    def _service(self, pusher_subs):
        return PubSubPushService(
            logger=self.logger,
            auth_service=self.auth_service,
            pusher_subs=pusher_subs,
            google_chat_processor_service=self.chat_processor,
            gerrit_processor_service=self.gerrit_processor,
        )

    def _assert_nothing_processed(self):
        self.chat_processor.process_event.assert_not_called()
        self.gerrit_processor.store_payload.assert_not_called()

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
                    self.service.receive_gerrit,
                ):
                    outcome = await receive(_BEARER, envelope)

                    self.assertEqual(outcome, PubSubPushOutcome.RETRY)
        self._assert_nothing_processed()


if __name__ == "__main__":
    unittest.main()
