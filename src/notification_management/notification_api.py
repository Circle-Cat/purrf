from flask import Blueprint, request
from http import HTTPStatus
from src.notification_management.microsoft_chat_watcher import (
    subscribe_chat_messages,
)
from src.common.api_response_wrapper import api_response

notification_bp = Blueprint("notification", __name__, url_prefix="/api")


@notification_bp.route("/microsoft/chat/subscribe", methods=["POST"])
async def subscribe_microsoft_chat_messages():
    """
    API endpoint to subscribe to Microsoft Teams chat message events.

    This endpoint registers a webhook subscription for receiving Microsoft Teams chat message notifications
    for a specified chat. If a valid subscription already exists, it will be reused; otherwise, a new one
    will be created.

    Request JSON Payload:
        {
            "chat_id": "string",  # Required. Microsoft Teams chat ID (e.g., "19:meeting_ID@thread.skype")
            "notification_url": "string",  # Required. Endpoint to receive message change notifications
            "lifecycle_notification_url": "string"  # Required. Endpoint to receive subscription lifecycle events
        }

    Returns:
        JSON response with:
        - success (bool): Whether the subscription was successful.
        - message (str): Description of what happened (e.g., subscription reused or created).
        - data (dict): Metadata including subscription ID, chat ID, and expiration timestamp.
        - status_code (int): HTTP 201 if successful.
    """
    data = request.get_json()
    chat_id = data.get("chat_id")
    notification_url = data.get("notification_url")
    lifecycle_notification_url = data.get("lifecycle_notification_url")

    message, data = await subscribe_chat_messages(
        chat_id, notification_url, lifecycle_notification_url
    )
    return api_response(
        success=True,
        message=message,
        data=data,
        status_code=HTTPStatus.CREATED,
    )
