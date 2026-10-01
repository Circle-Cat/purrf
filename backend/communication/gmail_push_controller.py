import base64
import json
from http import HTTPStatus

from fastapi import APIRouter, BackgroundTasks, Request, Response

from backend.common.api_endpoints import GMAIL_PUSH_ENDPOINT
from backend.communication.gmail_sync_service import PushOutcome


class GmailPushController:
    """The endpoint Gmail change notifications arrive on, via Pub/Sub push.

    The Cloudflare Worker verifies the Google OIDC token at the edge; it is
    verified again here because this route is exempt from the session
    middleware.

    The status code is the entire protocol with Pub/Sub: 503 only for errors a
    redelivery can fix, 403 for a failed token check, 200 otherwise. The
    cursor design lets any later push catch up on what an earlier one missed,
    so a push that cannot be read is acknowledged rather than retried.
    """

    def __init__(self, logger, gmail_sync_service, database, auth_service, pusher_subs):
        """
        Args:
            logger: Logger instance.
            gmail_sync_service (GmailSyncService): Applies a push to the mailbox.
            database: Async session provider.
            auth_service: Verifies the Google OIDC token on the request.
            pusher_subs (frozenset[str]): Service account subjects allowed to push.
        """
        self.logger = logger
        self.gmail_sync_service = gmail_sync_service
        self.database = database
        self.auth_service = auth_service
        self.pusher_subs = pusher_subs
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

        An expired cursor answers 200 at once and runs the full resync after
        the response, since it outlasts Pub/Sub's ack deadline.
        """
        authorization = request.headers.get("Authorization", "")
        if not authorization.startswith("Bearer "):
            self.logger.warning("[GmailPush] request carried no token; refusing")
            return Response(status_code=HTTPStatus.FORBIDDEN)

        try:
            claims = self.auth_service.verify_google_token(
                authorization.removeprefix("Bearer ")
            )
        except ValueError as e:
            self.logger.warning("[GmailPush] token rejected: %s", e)
            return Response(status_code=HTTPStatus.FORBIDDEN)

        if not self.pusher_subs:
            self.logger.warning(
                "[GmailPush] NOTIFICATION_PUSHER_SUBS is missing or empty -- "
                "refusing every caller until it is configured"
            )
            return Response(status_code=HTTPStatus.FORBIDDEN)

        if claims.get("sub") not in self.pusher_subs:
            self.logger.warning(
                "[GmailPush] token sub is not a provisioned pusher; refusing"
            )
            return Response(status_code=HTTPStatus.FORBIDDEN)

        try:
            envelope = await request.json()
            payload = json.loads(base64.b64decode(envelope["message"]["data"]))
            email_address = str(payload["emailAddress"]).lower()
            history_id = int(payload["historyId"])
        except (KeyError, TypeError, ValueError) as error:
            self.logger.warning("[GmailPush] unreadable push acked: %s", error)
            return Response(status_code=HTTPStatus.OK)

        try:
            async with self.database.session() as session:
                outcome = await self.gmail_sync_service.handle_push(
                    session, email_address, history_id
                )
        except Exception:
            self.logger.exception("[GmailPush] push for %s failed", email_address)
            return Response(status_code=HTTPStatus.SERVICE_UNAVAILABLE)

        if outcome == PushOutcome.RETRY:
            return Response(status_code=HTTPStatus.SERVICE_UNAVAILABLE)
        if outcome == PushOutcome.RESYNC:
            background_tasks.add_task(self._run_scheduled_resync)
        return Response(status_code=HTTPStatus.OK)

    async def _run_scheduled_resync(self):
        try:
            async with self.database.session() as session:
                await self.gmail_sync_service.run_scheduled_resync(session)
        except Exception:
            self.logger.exception("[GmailPush] automatic full resync failed")
