from http import HTTPStatus
from fastapi import APIRouter
from backend.common.fast_api_response_wrapper import api_response
from backend.common.user_role import UserRole
from backend.utils.permission_decorators import authenticate
from backend.common.api_endpoints import PUBSUB_SYNC_PULL_ENDPOINT


class ConsumerController:
    def __init__(self, pubsub_sync_pull_service):
        """
        Initialize the ConsumerController.

        Args:
            pubsub_sync_pull_service: PubSubSyncPullService instance for one-shot sync pull.
        """
        self.pubsub_sync_pull_service = pubsub_sync_pull_service

        self.router = APIRouter(tags=["consumers"])

        self.router.add_api_route(
            PUBSUB_SYNC_PULL_ENDPOINT,
            endpoint=authenticate(roles=[UserRole.INFRA_ADMIN, UserRole.CRON_RUNNER])(
                self.sync_pull_all
            ),
            methods=["POST"],
            response_model=dict,
        )

    async def sync_pull_all(self):
        """
        One-shot synchronous pull from all three Pub/Sub subscriptions.
        Pulls pending messages, processes them, acks, and returns.
        Designed to be called periodically by a CronJob.
        """
        results = self.pubsub_sync_pull_service.sync_pull_all()
        return api_response(
            success=True,
            message="Sync pull completed.",
            data=results,
            status_code=HTTPStatus.OK,
        )
