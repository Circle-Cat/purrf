"""The endpoints Google Chat, Microsoft Teams and Gerrit events arrive on, via Pub/Sub push.

Everything they decide is in ``PubSubPushService``; this only turns the
request into that call and the outcome into a status code.
"""

from http import HTTPStatus

from fastapi import APIRouter, Request, Response

from backend.common.api_endpoints import (
    PUBSUB_PUSH_GERRIT_ENDPOINT,
    PUBSUB_PUSH_GOOGLE_CHAT_ENDPOINT,
    PUBSUB_PUSH_MICROSOFT_CHAT_ENDPOINT,
)
from backend.consumers.pubsub_push_service import PubSubPushOutcome

_STATUS = {
    PubSubPushOutcome.ACK: HTTPStatus.OK,
    PubSubPushOutcome.RETRY: HTTPStatus.SERVICE_UNAVAILABLE,
    PubSubPushOutcome.REFUSED: HTTPStatus.FORBIDDEN,
}


async def _read_envelope(request: Request):
    """The JSON body, or None when it is not JSON."""
    try:
        return await request.json()
    except ValueError:
        return None


class PubSubPushController:
    """Carries a Pub/Sub push to the service that acts on it."""

    def __init__(self, pubsub_push_service):
        """
        Args:
            pubsub_push_service (PubSubPushService): Decides what the push
                means and applies it.
        """
        self.pubsub_push_service = pubsub_push_service
        self.router = APIRouter(tags=["pubsub-push"])
        self.router.add_api_route(
            PUBSUB_PUSH_GOOGLE_CHAT_ENDPOINT,
            endpoint=self.push_google_chat,
            methods=["POST"],
            response_model=None,
        )
        self.router.add_api_route(
            PUBSUB_PUSH_MICROSOFT_CHAT_ENDPOINT,
            endpoint=self.push_microsoft_chat,
            methods=["POST"],
            response_model=None,
        )
        self.router.add_api_route(
            PUBSUB_PUSH_GERRIT_ENDPOINT,
            endpoint=self.push_gerrit,
            methods=["POST"],
            response_model=None,
        )

    async def push_google_chat(self, request: Request) -> Response:
        """Apply a Google Chat event from a Pub/Sub push envelope.

        Returns:
            Response: 403 for a caller the service refuses, 503 when a
                redelivery can help, 200 otherwise.
        """
        outcome = await self.pubsub_push_service.receive_google_chat(
            request.headers.get("Authorization", ""), await _read_envelope(request)
        )
        return Response(status_code=_STATUS[outcome])

    async def push_microsoft_chat(self, request: Request) -> Response:
        """Apply a Microsoft Teams chat change notification from a Pub/Sub push envelope.

        Returns:
            Response: 403 for a caller the service refuses, 503 when a
                redelivery can help, 200 otherwise.
        """
        outcome = await self.pubsub_push_service.receive_microsoft_chat(
            request.headers.get("Authorization", ""), await _read_envelope(request)
        )
        return Response(status_code=_STATUS[outcome])

    async def push_gerrit(self, request: Request) -> Response:
        """Apply a Gerrit event from a Pub/Sub push envelope.

        Returns:
            Response: 403 for a caller the service refuses, 503 when a
                redelivery can help, 200 otherwise.
        """
        outcome = await self.pubsub_push_service.receive_gerrit(
            request.headers.get("Authorization", ""), await _read_envelope(request)
        )
        return Response(status_code=_STATUS[outcome])
