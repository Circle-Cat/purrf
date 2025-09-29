from http import HTTPStatus
from flask import Blueprint
from backend.common.api_response_wrapper import api_response

consumers_bp = Blueprint("consumers", __name__, url_prefix="/api")


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

    def register_routes(self, blueprint):
        """
        Register all historical data backfill routes to the given Flask blueprint.

        Args:
            blueprint: Flask Blueprint object to register routes on.
        """
        blueprint.add_url_rule(
            "/microsoft/pull/<project_id>/<subscription_id>",
            view_func=self.start_microsoft_pulling,
            methods=["POST"],
        )
        blueprint.add_url_rule(
            "/google/chat/pull/<project_id>/<subscription_id>",
            view_func=self.start_google_chat_pulling,
            methods=["POST"],
        )
        blueprint.add_url_rule(
            "/gerrit/pull/<project_id>/<subscription_id>",
            view_func=self.start_gerrit_pulling,
            methods=["POST"],
        )
        blueprint.add_url_rule(
            "/pubsub/pull/status/<project_id>/<subscription_id>",
            view_func=self.check_pulling_messages,
            methods=["GET"],
        )
        blueprint.add_url_rule(
            "/pubsub/pull/<project_id>/<subscription_id>",
            view_func=self.stop_pulling,
            methods=["DELETE"],
        )

    def start_google_chat_pulling(self, project_id, subscription_id):
        """
        HTTP POST endpoint to initiate message pulling from a given Pub/Sub subscription.

        Args:
            project_id (str): The Google Cloud project ID, passed as a URL path parameter.
            subscription_id (str): The Pub/Sub subscription ID, passed as a URL path parameter.

        Returns:
            Response: A standardized JSON response indicating that the pull process has started.
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

    def start_microsoft_pulling(self, project_id, subscription_id):
        """
        HTTP POST endpoint to trigger the message pulling process for a given
        Pub/Sub subscription.

        Args:
            project_id (str): The Google Cloud project ID from URL path.
            subscription_id (str): The Pub/Sub subscription ID from URL path.

        Returns:
            Response: JSON response indicating success status and HTTP 200 code.
        """
        self.microsoft_message_processor_service.pull_microsoft_message(
            project_id, subscription_id
        )

        return api_response(
            success=True,
            message="Successfully.",
            data=None,
            status_code=HTTPStatus.OK,
        )

    def start_gerrit_pulling(self, project_id: str, subscription_id: str):
        """
        HTTP POST endpoint to trigger the Gerrit Pub/Sub pulling process
        for a given project and subscription.

        Args:
            project_id (str): The Google Cloud project ID from URL path.
            subscription_id (str): The Pub/Sub subscription ID from URL path.

        Returns:
            JSON response with pull status and HTTP 200 code.
        """
        self.gerrit_processor_service.pull_gerrit(project_id, subscription_id)
        return api_response(
            success=True,
            message="Gerrit pull started.",
            data=None,
            status_code=HTTPStatus.OK,
        )

    def check_pulling_messages(self, project_id, subscription_id):
        """
        HTTP GET endpoint to retrieve the current message pulling status for a given
        Pub/Sub subscription.

        Args:
            project_id (str): The Google Cloud project ID, passed as a URL path parameter.
            subscription_id (str): The Pub/Sub subscription ID, passed as a URL path parameter.

        Returns:
            Response: A JSON response containing the pulling task status data, success flag,
                    message, and HTTP status code 200 (OK).
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

    def stop_pulling(self, project_id, subscription_id):
        """
        HTTP DELETE endpoint to stop the message pulling process for a given
        Pub/Sub subscription.

        Args:
            project_id (str): The Google Cloud project ID, provided as a URL path parameter.
            subscription_id (str): The Pub/Sub subscription ID, provided as a URL path parameter.

        Returns:
            Response: A JSON response indicating whether the stopping operation succeeded,
                    including the final pulling status, a success flag, and HTTP 200 status.
        """
        data = self.pubsub_pull_manager.stop_pulling_process(
            project_id, subscription_id
        )
        return api_response(
            success=True,
            message="Successfully.",
            data=data,
            status_code=HTTPStatus.OK,
        )
