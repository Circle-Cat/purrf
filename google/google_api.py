"""google chat service"""

from flask import jsonify, Blueprint, request
from google.pubsub_subscriber_store import pull_messages
from http import HTTPStatus
import http.client
from http import HTTPStatus
from google.constants import PULL_PROCESS_STARTED_MSG

google_bp = Blueprint("google", __name__)


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
