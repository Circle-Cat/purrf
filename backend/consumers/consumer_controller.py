from http import HTTPStatus
from fastapi import APIRouter
from backend.common.fast_api_response_wrapper import api_response
from backend.common.user_role import UserRole
from backend.utils.permission_decorators import authenticate
from backend.common.api_endpoints import (
    MICROSOFT_PULL_ENDPOINT,
    GOOGLE_CHAT_PULL_ENDPOINT,
    GERRIT_PULL_ENDPOINT,
    PUBSUB_STATUS_ENDPOINT,
    PUBSUB_STOP_ENDPOINT,
)


class ConsumerController:
    def __init__(
        self,
        microsoft_message_processor_service,
        google_chat_processor_service,
        gerrit_processor_service,
        pubsub_pull_manager,
    ):
        """
        Initialize the ConsumerController with required dependencies.

        Args:
            microsoft_message_processor_service: MicrosoftMessageProcessorService instance.
            google_chat_processor_service: GoogleChatProcessorService instance.
            gerrit_processor_service: GerritProcessorService instance.
            pubsub_pull_manager: PubSubPullManager instance.
        """
        self.microsoft_message_processor_service = microsoft_message_processor_service
        self.google_chat_processor_service = google_chat_processor_service
        self.gerrit_processor_service = gerrit_processor_service
        self.pubsub_pull_manager = pubsub_pull_manager

        self.router = APIRouter(tags=["consumers"])

        self.router.add_api_route(
            MICROSOFT_PULL_ENDPOINT,
            endpoint=authenticate(roles=[UserRole.ADMIN])(self.start_microsoft_pulling),
            methods=["POST"],
            response_model=dict,
        )

        self.router.add_api_route(
            GOOGLE_CHAT_PULL_ENDPOINT,
            endpoint=authenticate(roles=[UserRole.ADMIN])(
                self.start_google_chat_pulling
            ),
            methods=["POST"],
            response_model=dict,
        )

        self.router.add_api_route(
            GERRIT_PULL_ENDPOINT,
            endpoint=authenticate(roles=[UserRole.ADMIN])(self.start_gerrit_pulling),
            methods=["POST"],
            response_model=dict,
        )

        self.router.add_api_route(
            PUBSUB_STATUS_ENDPOINT,
            endpoint=authenticate(roles=[UserRole.ADMIN])(self.check_pulling_messages),
            methods=["GET"],
            response_model=dict,
        )

        self.router.add_api_route(
            PUBSUB_STOP_ENDPOINT,
            endpoint=authenticate(roles=[UserRole.ADMIN])(self.stop_pulling),
            methods=["DELETE"],
            response_model=dict,
        )

    async def start_google_chat_pulling(self, project_id: str, subscription_id: str):
        """
        HTTP POST endpoint to initiate message pulling from a given Pub/Sub subscription (Google Chat Data).
        """
        self.google_chat_processor_service.pull_messages(project_id, subscription_id)

        return api_response(
            success=True,
            message=(
                f"Started pulling google chat messages for subscription "
                f"'{subscription_id}' in project '{project_id}'."
            ),
            data=None,
            status_code=HTTPStatus.ACCEPTED,
        )

    async def start_microsoft_pulling(self, project_id: str, subscription_id: str):
        """
        HTTP POST endpoint to trigger the message pulling process for a given
        Pub/Sub subscription (Microsoft Teams Chat Data).
        """
        self.microsoft_message_processor_service.pull_microsoft_message(
            project_id, subscription_id
        )

        return api_response(
            success=True,
            message="Successfully started Microsoft pulling.",
            data=None,
            status_code=HTTPStatus.OK,
        )

    async def start_gerrit_pulling(self, project_id: str, subscription_id: str):
        """
        HTTP POST endpoint to trigger the Gerrit Pub/Sub pulling process.
        """
        self.gerrit_processor_service.pull_gerrit(project_id, subscription_id)
        return api_response(
            success=True,
            message="Gerrit pull started.",
            data=None,
            status_code=HTTPStatus.OK,
        )

    async def check_pulling_messages(self, project_id: str, subscription_id: str):
        """
        HTTP GET endpoint to retrieve the current message pulling status.
        """
        data = self.pubsub_pull_manager.check_pulling_status(
            project_id, subscription_id
        )
        return api_response(
            success=True,
            message="Pulling task status retrieved successfully.",
            data=data,
            status_code=HTTPStatus.OK,
        )

    async def stop_pulling(self, project_id: str, subscription_id: str):
        """
        HTTP DELETE endpoint to stop the message pulling process for a given
        Pub/Sub subscription.
        """
        data = self.pubsub_pull_manager.stop_pulling_process(
            project_id, subscription_id
        )
        return api_response(
            success=True,
            message="Successfully stopped pulling.",
            data=data,
            status_code=HTTPStatus.OK,
        )
