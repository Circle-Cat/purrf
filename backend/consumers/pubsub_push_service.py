"""What a Google Chat, Microsoft Teams or Gerrit event arriving by Pub/Sub push means.

These are the same events the hourly sync pull drains; push delivers each one
as it is published. The Cloudflare Worker verifies the Google OIDC token at the
edge; it is verified again here because the routes are exempt from the session
middleware.

Any failure past the caller check answers RETRY, including a payload that
cannot be decoded. That matches the sync pull, which nacks such a message: the
subscription's dead-letter policy is what finally sets a poison message aside
where someone can inspect it.
"""

import asyncio
import base64
import json
from enum import StrEnum

from backend.common.constants import (
    ALL_GOOGLE_CHAT_EVENT_TYPES,
    EXPIRATION_REMINDER_EVENT,
)


class PubSubPushOutcome(StrEnum):
    """What the push endpoint tells Pub/Sub: ACK drops the message, RETRY redelivers it."""

    ACK = "ack"
    RETRY = "retry"
    REFUSED = "refused"


class PubSubPushService:
    """Checks who sent a push, decodes it, and hands it to the event's processor."""

    def __init__(
        self,
        logger,
        auth_service,
        pusher_subs,
        google_chat_processor_service,
        gerrit_processor_service,
        microsoft_chat_message_util,
    ):
        """
        Args:
            logger: Logger instance.
            auth_service: Verifies the Google OIDC token on the request.
            pusher_subs (frozenset[str]): Service account subjects allowed to
                push. Empty refuses everybody.
            google_chat_processor_service (GoogleChatProcessorService): Stores
                Google Chat events and renews the Chat subscription.
            gerrit_processor_service (GerritProcessorService): Stores Gerrit
                events.
            microsoft_chat_message_util (MicrosoftChatMessageUtil): Fetches a
                changed Teams message from Graph and stores it.
        """
        self.logger = logger
        self.auth_service = auth_service
        self.pusher_subs = pusher_subs
        self.google_chat_processor_service = google_chat_processor_service
        self.gerrit_processor_service = gerrit_processor_service
        self.microsoft_chat_message_util = microsoft_chat_message_util

    def _refuse(self, reason: str) -> PubSubPushOutcome:
        self.logger.warning("[PubSubPush] %s; refusing", reason)
        return PubSubPushOutcome.REFUSED

    def _caller_refusal(self, authorization: str) -> PubSubPushOutcome | None:
        """REFUSED for any caller that is not a provisioned pusher, else None."""
        if not authorization.startswith("Bearer "):
            return self._refuse("request carried no token")

        try:
            claims = self.auth_service.verify_google_token(
                authorization.removeprefix("Bearer ")
            )
        except ValueError as error:
            return self._refuse(f"token rejected: {error}")

        if not self.pusher_subs:
            return self._refuse(
                "NOTIFICATION_PUSHER_SUBS is missing or empty -- refusing every "
                "caller until it is configured"
            )

        if claims.get("sub") not in self.pusher_subs:
            return self._refuse("token sub is not a provisioned pusher")

        return None

    async def _receive(
        self, source: str, authorization: str, envelope, process_fn
    ) -> PubSubPushOutcome:
        """Await ``process_fn(data, attributes)`` on the message a push envelope carries."""
        refusal = self._caller_refusal(authorization)
        if refusal is not None:
            return refusal

        try:
            message = envelope["message"]
            data = json.loads(base64.b64decode(message["data"]))
            attributes = dict(message.get("attributes") or {})
        except (KeyError, TypeError, ValueError) as error:
            self.logger.error("[PubSubPush] unreadable %s push: %s", source, error)
            return PubSubPushOutcome.RETRY

        try:
            await process_fn(data, attributes)
        except Exception:
            self.logger.exception(
                "[PubSubPush] %s message %s failed",
                source,
                message.get("messageId"),
            )
            return PubSubPushOutcome.RETRY
        return PubSubPushOutcome.ACK

    async def _process_google_chat(self, data: dict, attributes: dict):
        message_type = attributes.get("ce-type")
        # An event type nothing handles would fail on every redelivery, so it
        # is dropped here rather than raised.
        if (
            message_type != EXPIRATION_REMINDER_EVENT
            and message_type not in ALL_GOOGLE_CHAT_EVENT_TYPES
        ):
            self.logger.warning(
                "[PubSubPush] Dropping unsupported Google Chat event: %s",
                message_type,
            )
            return
        # Synchronous Redis and Google API calls; a worker thread keeps the
        # event loop free.
        await asyncio.to_thread(
            self.google_chat_processor_service.process_event, data, attributes
        )

    async def _process_gerrit(self, data: dict, attributes: dict):
        # Synchronous Redis calls, likewise on a worker thread.
        await asyncio.to_thread(self.gerrit_processor_service.store_payload, data)

    async def _process_microsoft_chat(self, data: dict, attributes: dict):
        await self.microsoft_chat_message_util.sync_near_real_time_message_to_redis(
            data.get("changeType"), data.get("resource")
        )

    async def receive_google_chat(
        self, authorization: str, envelope
    ) -> PubSubPushOutcome:
        """Apply a Google Chat event from a Pub/Sub push envelope.

        Args:
            authorization (str): The request's Authorization header, or "".
            envelope: The decoded JSON body, or None when it could not be read.

        Returns:
            PubSubPushOutcome: REFUSED for an unknown caller; RETRY when the
                message could not be read or processed; ACK otherwise,
                including for an event type nothing handles.
        """
        return await self._receive(
            "Google Chat", authorization, envelope, self._process_google_chat
        )

    async def receive_microsoft_chat(
        self, authorization: str, envelope
    ) -> PubSubPushOutcome:
        """Apply a Microsoft Teams chat change notification from a Pub/Sub push envelope.

        Args:
            authorization (str): The request's Authorization header, or "".
            envelope: The decoded JSON body, or None when it could not be read.

        Returns:
            PubSubPushOutcome: REFUSED for an unknown caller; RETRY when the
                message could not be read or processed, including a change type
                nothing handles; ACK otherwise.
        """
        return await self._receive(
            "Microsoft Teams", authorization, envelope, self._process_microsoft_chat
        )

    async def receive_gerrit(self, authorization: str, envelope) -> PubSubPushOutcome:
        """Apply a Gerrit event from a Pub/Sub push envelope.

        Args:
            authorization (str): The request's Authorization header, or "".
            envelope: The decoded JSON body, or None when it could not be read.

        Returns:
            PubSubPushOutcome: REFUSED for an unknown caller; RETRY when the
                message could not be read or processed; ACK otherwise.
        """
        return await self._receive(
            "Gerrit", authorization, envelope, self._process_gerrit
        )
