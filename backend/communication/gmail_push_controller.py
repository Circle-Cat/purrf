"""The endpoint Gmail change notifications arrive on, via Pub/Sub push.

Everything it decides is in ``GmailPushService``; this only turns the request
into that call and the outcome into a status code.
"""

from http import HTTPStatus

from fastapi import APIRouter, BackgroundTasks, Request, Response

from backend.common.api_endpoints import GMAIL_PUSH_ENDPOINT
from backend.communication.gmail_sync_service import PushOutcome

_STATUS = {
    PushOutcome.ACK: HTTPStatus.OK,
    PushOutcome.RESYNC: HTTPStatus.OK,
    PushOutcome.RETRY: HTTPStatus.SERVICE_UNAVAILABLE,
    PushOutcome.REFUSED: HTTPStatus.FORBIDDEN,
}


class GmailPushController:
    """Carries a Pub/Sub push to the service that acts on it."""

    def __init__(self, gmail_push_service, database):
        """
        Args:
            gmail_push_service (GmailPushService): Decides what the push means
                and applies it.
            database: Async session provider.
        """
        self.gmail_push_service = gmail_push_service
        self.database = database
        self.router = APIRouter(tags=["gmail-push"])
        self.router.add_api_route(
            GMAIL_PUSH_ENDPOINT,
            endpoint=self.push,
            methods=["POST"],
            response_model=None,
        )

    async def push(
        self, request: Request, background_tasks: BackgroundTasks
    ) -> Response:
        """Apply a Gmail change notification from a Pub/Sub push envelope.

        A RESYNC outcome answers at once and runs the full resync after the
        response, since it outlasts Pub/Sub's ack deadline.

        Returns:
            Response: 403 for a caller the service refuses, 503 when a
                redelivery can help, 200 otherwise.
        """
        try:
            envelope = await request.json()
        except ValueError:
            envelope = None

        async with self.database.session() as session:
            outcome = await self.gmail_push_service.receive(
                session, request.headers.get("Authorization", ""), envelope
            )
        if outcome == PushOutcome.RESYNC:
            background_tasks.add_task(self.gmail_push_service.run_scheduled_resync)
        return Response(status_code=_STATUS[outcome])
