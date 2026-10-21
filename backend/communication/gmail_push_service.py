"""What a Gmail change notification arriving by Pub/Sub push means.

The Cloudflare Worker verifies the Google OIDC token at the edge; it is
verified again here because the route is exempt from the session middleware.

The outcome is the entire protocol with Pub/Sub: RETRY only for errors a
redelivery can fix, REFUSED for a failed token check, ACK otherwise. The
cursor design lets any later push catch up on what an earlier one missed, so
a push that cannot be read is acknowledged rather than retried.
"""

import base64
import json

from backend.communication.gmail_sync_service import PushOutcome


class GmailPushService:
    """Checks who sent a push, reads it, and hands it to the mailbox sync."""

    def __init__(self, logger, gmail_sync_service, auth_service, pusher_subs, database):
        """
        Args:
            logger: Logger instance.
            gmail_sync_service (GmailSyncService): Applies a push to the mailbox.
            auth_service: Verifies the Google OIDC token on the request.
            pusher_subs (frozenset[str]): Service account subjects allowed to
                push. Empty refuses everybody.
            database: Async session provider, for the resync that runs after
                the response.
        """
        self.logger = logger
        self.gmail_sync_service = gmail_sync_service
        self.auth_service = auth_service
        self.pusher_subs = pusher_subs
        self.database = database

    def _refuse(self, reason: str) -> PushOutcome:
        self.logger.warning("[GmailPush] %s; refusing", reason)
        return PushOutcome.REFUSED

    def _caller_refusal(self, authorization: str) -> PushOutcome | None:
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

    async def receive(self, session, authorization: str, envelope) -> PushOutcome:
        """Apply a Gmail change notification from a Pub/Sub push envelope.

        Args:
            session (AsyncSession): A session this call owns. Committed by the
                sync.
            authorization (str): The request's Authorization header, or "".
            envelope: The decoded JSON body, or None when it could not be read.

        Returns:
            PushOutcome: REFUSED for an unknown caller; RETRY when Gmail was
                unavailable or anything unexpected failed; RESYNC when the
                cursor expired and ``run_scheduled_resync`` must run after the
                response; ACK otherwise, including for an unreadable push.
        """
        refusal = self._caller_refusal(authorization)
        if refusal is not None:
            return refusal

        try:
            payload = json.loads(base64.b64decode(envelope["message"]["data"]))
            email_address = str(payload["emailAddress"]).lower()
            history_id = int(payload["historyId"])
        except (KeyError, TypeError, ValueError) as error:
            self.logger.warning("[GmailPush] unreadable push acked: %s", error)
            return PushOutcome.ACK

        try:
            return await self.gmail_sync_service.handle_push(
                session, email_address, history_id
            )
        except Exception:
            # Includes the IntegrityError two racing first-ever pushes raise;
            # the redelivery finds the row the other one created.
            self.logger.exception("[GmailPush] push for %s failed", email_address)
            return PushOutcome.RETRY

    async def run_scheduled_resync(self):
        """Run the full resync a RESYNC outcome asked for, on a session of its own.

        Runs after the response, so a failure is logged rather than raised; the
        sync has already recorded and alerted on it.
        """
        try:
            async with self.database.session() as session:
                await self.gmail_sync_service.run_scheduled_resync(session)
        except Exception:
            self.logger.exception("[GmailPush] automatic full resync failed")
