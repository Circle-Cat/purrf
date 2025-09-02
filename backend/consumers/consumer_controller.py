from http import HTTPStatus
from flask import Blueprint
from backend.consumers.pubsub_pull_manager import (
    check_pulling_status,
    stop_pulling_process,
)

from backend.consumers.gerrit_consumer import pull_gerrit
from backend.common.api_response_wrapper import api_response

consumers_bp = Blueprint("consumers", __name__, url_prefix="/api")


class ConsumerController:
    def __init__(
        self, microsoft_message_processor_service, google_chat_processor_service
    ):
        """
        Initialize the ConsumerController with required dependencies.

        Args:
            microsoft_message_processor_service: MicrosoftMessageProcessorService instance.
            google_chat_processor_service: GoogleChatProcessorService instance.
        """
        self.microsoft_message_processor_service = microsoft_message_processor_service
        self.google_chat_processor_service = google_chat_processor_service

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


@consumers_bp.route(
    "/pubsub/pull/status/<project_id>/<subscription_id>", methods=["GET"]
)
def check_pulling_messages(project_id, subscription_id):
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
    data = check_pulling_status(project_id, subscription_id)
    return api_response(
        success=True,
        message="Pulling task status retrieved successfully.",
        data=data,
        status_code=HTTPStatus.OK,
    )


@consumers_bp.route("/pubsub/pull/<project_id>/<subscription_id>", methods=["DELETE"])
def stop_pulling(project_id, subscription_id):
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
    data = stop_pulling_process(project_id, subscription_id)
    return api_response(
        success=True,
        message="Successfully.",
        data=data,
        status_code=HTTPStatus.OK,
    )


@consumers_bp.route("/gerrit/pull/<project_id>/<subscription_id>", methods=["POST"])
def start_gerrit_pulling(project_id: str, subscription_id: str):
    """
    HTTP POST endpoint to trigger the Gerrit Pub/Sub pulling process
    for a given project and subscription.

    Args:
        project_id (str): The Google Cloud project ID from URL path.
        subscription_id (str): The Pub/Sub subscription ID from URL path.

    Returns:
        JSON response with pull status and HTTP 200 code.
    """
    pull_gerrit(project_id, subscription_id)
    return api_response(
        success=True,
        message="Gerrit pull started.",
        data=None,
        status_code=HTTPStatus.OK,
    )
