"""google chat service"""

from flask import jsonify, Blueprint
from google.fetch_history_chat_message import fetch_history_messages
import http.client
from concurrent.futures import ThreadPoolExecutor

google_bp = Blueprint("google", __name__)

executor = ThreadPoolExecutor(max_workers=5)


@google_bp.route("/api/chat/spaces/messages")
def history_messages():
    """API endpoint to trigger the fetching of messages for all SPACE type chat spaces and store them in Redis asynchronously."""

    executor.submit(fetch_history_messages)
    return jsonify({
        "message": "Message retrieval triggered asynchronously."
    }), http.client.ACCEPTED
