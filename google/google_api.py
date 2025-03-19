"""google chat service"""

from flask import jsonify, Blueprint, request
from google.fetch_history_chat_message import fetch_history_messages
from google.pubsub_subscriber_store import pull_messages
from http import HTTPStatus
from google.chat_utils import get_chat_spaces
import http.client
import threading
from concurrent.futures import ThreadPoolExecutor
from google.constants import (
    PULL_PROCESS_STARTED_MSG,
    MISSING_FIELDS_MSG,
)

google_bp = Blueprint("google", __name__)

executor = ThreadPoolExecutor(max_workers=5)


@google_bp.route("/api/chat/spaces/messages")
def history_messages():
    """API endpoint to trigger the fetching of messages for all SPACE type chat spaces and store them in Redis asynchronously."""

    executor.submit(fetch_history_messages)
    return jsonify({
        "message": "Message retrieval triggered asynchronously."
    }), http.client.ACCEPTED


@google_bp.route("/api/chat/spaces")
def get_chat_spaces_route():
    """API endpoint to retrieve chat spaces of a specified type and page size."""

    space_type = request.args.get("space_type", "SPACE")
    page_size = int(request.args.get("page_size", 100))

    spaces = get_chat_spaces(space_type, page_size)
    return jsonify({"spaces": spaces}), 200


@google_bp.route("/api/chat/pull", methods=["POST"])
def api_chat_pull_route():
    data = request.get_json() or {}
    subscription_id = data.get("subscription_id")
    project_id = data.get("project_id")

    if not subscription_id or not project_id:
        missing = []
        if not subscription_id:
            missing.append("subscription_id")
        if not project_id:
            missing.append("project_id")
        return jsonify({
            "status": MISSING_FIELDS_MSG.format(fields=", ".join(missing))
        }), HTTPStatus.BAD_REQUEST

    thread = threading.Thread(target=pull_messages, args=(project_id, subscription_id))
    thread.daemon = True
    thread.start()

    return jsonify({
        "status": PULL_PROCESS_STARTED_MSG.format(
            subscription_id=subscription_id, project_id=project_id
        )
    }), HTTPStatus.ACCEPTED
