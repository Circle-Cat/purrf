"""google chat service"""

from flask import jsonify, Blueprint, request
from google.fetch_history_chat_message import fetch_history_messages
from google.chat_utils import get_chat_spaces
from http import HTTPStatus

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
