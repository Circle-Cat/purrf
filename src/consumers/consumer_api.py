from flask import Blueprint
from http import HTTPStatus
from src.consumers.pubsub_pull_manager import check_pulling_status, stop_pulling_process
from src.common.api_response_wrapper import api_response

consumers_bp = Blueprint("consumers", __name__, url_prefix="/api")


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
