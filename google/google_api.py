"""google chat service"""

from flask import jsonify, Blueprint, request
from google.pubsub_subscriber_store import pull_messages
from http import HTTPStatus
from src.utils.google_chat_utils import get_chat_spaces
import http.client
from http import HTTPStatus
from concurrent.futures import ThreadPoolExecutor
from google.constants import PULL_PROCESS_STARTED_MSG

google_bp = Blueprint("google", __name__)


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
