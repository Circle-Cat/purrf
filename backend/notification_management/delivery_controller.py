import base64
import json
from http import HTTPStatus

from fastapi import APIRouter, Request, Response

from backend.common.api_endpoints import NOTIFICATION_DELIVER_ENDPOINT
from backend.common.logger import get_logger
from backend.notification_management.delivery_service import DeliveryOutcome

logger = get_logger()


class NotificationDeliveryController:
    """The endpoint Pub/Sub push targets, via the Cloudflare Worker.

    Identity is enforced at the edge: the Worker verifies the Google OIDC
    token and only then forwards with a CF Access service token, so this
    route trusts "the request reached me" the same way every other route
    behind Access does.

    The status code is the entire protocol with Pub/Sub, so every branch
    that a redelivery could not improve returns 200.
    """

    def __init__(self, delivery_service, publisher, topic_path, database):
        """
        Args:
            delivery_service (DeliveryService): Claims, renders and sends
                the notification named in the push envelope.
            publisher: Pub/Sub publisher client, reused to republish any
                straggler this pass turns up.
            topic_path (str): Fully qualified topic republished stragglers
                go to.
            database: Async session provider.
        """
        self.delivery_service = delivery_service
        self.publisher = publisher
        self.topic_path = topic_path
        self.database = database
        self.router = APIRouter(tags=["notification-delivery"])
        self.router.add_api_route(
            NOTIFICATION_DELIVER_ENDPOINT,
            endpoint=self.deliver,
            methods=["POST"],
            response_model=None,
        )

    async def deliver(self, request: Request) -> Response:
        """Deliver the notification named in a Pub/Sub push envelope."""
        envelope = await request.json()
        try:
            data = envelope["message"]["data"]
            notification_id = json.loads(base64.b64decode(data))["notification_id"]
        except (KeyError, TypeError, ValueError):
            logger.warning("[Delivery] unparseable envelope; acking")
            return Response(status_code=HTTPStatus.OK)

        async with self.database.session() as session:
            outcome = await self.delivery_service.deliver(session, notification_id)
            for straggler in await self.delivery_service.sweep_stragglers(session):
                self.publisher.publish(
                    self.topic_path,
                    json.dumps({"notification_id": straggler}).encode(),
                )

        if outcome is DeliveryOutcome.RETRY:
            return Response(status_code=HTTPStatus.SERVICE_UNAVAILABLE)
        return Response(status_code=HTTPStatus.OK)
