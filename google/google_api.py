"""google chat service"""

from flask import jsonify, Blueprint, request
from google.fetch_history_chat_message import fetch_history_messages
from google.pubsub_subscriber_store import pull_messages
from http import HTTPStatus
from src.utils.google_chat_utils import get_chat_spaces
from google.pubsub_publisher import subscribe_chat
import http.client
from http import HTTPStatus
from concurrent.futures import ThreadPoolExecutor
from google.constants import PULL_PROCESS_STARTED_MSG

google_bp = Blueprint("google", __name__)


@google_bp.route("/api/chat/spaces/messages", methods=["POST"])
def history_messages():
    """API endpoint to trigger the fetching of messages for all SPACE type chat spaces and store them in Redis asynchronously."""

    response = fetch_history_messages()
    return jsonify({"response": response}), HTTPStatus.OK


@google_bp.route("/api/chat/spaces", methods=["GET"])
def get_chat_spaces_route():
    """API endpoint to retrieve chat spaces of a specified type and page size."""

    space_type = request.args.get("space_type", "SPACE")
    page_size = int(request.args.get("page_size", 100))

    spaces = get_chat_spaces(space_type, page_size)
    return jsonify({"spaces": spaces}), HTTPStatus.OK


@google_bp.route("/api/chat/pull", methods=["POST"])
def api_chat_pull_route():
    data = request.get_json() or {}
    subscription_id = data.get("subscription_id")
    project_id = data.get("project_id")

    executor.submit(pull_messages, project_id, subscription_id)

    return jsonify({
        "status": PULL_PROCESS_STARTED_MSG.format(
            subscription_id=subscription_id, project_id=project_id
        )
    }), HTTPStatus.ACCEPTED


@google_bp.route("/api/chat/spaces/subscribe", methods=["POST"])
def subscribe():
    """API endpoint to subscribe to chat space events.

    Request JSON Payload:
        {
            "project_id": "your-project-id"
            "topic_id": "your-topic-id",
            "subscription_id": "your-subscription-id",
            "space_id": "your-space-id"
        }

    Returns:
        JSON response indicating success or failure of subscription.
    """
    data = request.get_json()
    project_id = data.get("project_id")
    topic_id = data.get("topic_id")
    subscription_id = data.get("subscription_id")
    space_id = data.get("space_id")

    success, response = subscribe_chat(
        project_id, topic_id, subscription_id, space_id, request_data=data
    )
    return jsonify({
        "space_id": space_id,
        "is_success": success,
        "response": response,
    }), HTTPStatus.OK
