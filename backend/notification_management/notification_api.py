from flask import Blueprint, request
from http import HTTPStatus
from backend.notification_management.microsoft_chat_watcher import (
    subscribe_chat_messages,
)
from backend.notification_management.google_chat_watcher import (
    create_workspaces_subscriptions,
)
from backend.notification_management.gerrit_watcher import GerritWatcher
from backend.common.api_response_wrapper import api_response
from backend.common.constants import EVENT_TYPES

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


@notification_bp.route("/google/chat/spaces/subscribe", methods=["POST"])
def subscribe():
    """API endpoint to subscribe to chat space events.

    Request JSON Payload:
        {
            "project_id": "your-project-id"
            "topic_id": "your-topic-id",
            "space_id": "your-space-id"
        }

    Returns:
        JSON response indicating success or failure of subscription.
    """
    data = request.get_json()
    project_id = data.get("project_id")
    topic_id = data.get("topic_id")
    space_id = data.get("space_id")
    event_types = EVENT_TYPES

    response = create_workspaces_subscriptions(
        project_id, topic_id, space_id, event_types
    )
    return api_response(
        success=True,
        message=response,
        status_code=HTTPStatus.CREATED,
    )


@notification_bp.route("/gerrit/webhook/register", methods=["POST"])
def register_gerrit_webhook():
    """
    Registers a Gerrit webhook for receiving change events.

    This endpoint uses the GerritWatcher class to create (or retrieve)
    a webhook subscription via Gerrit's Webhooks plugin. It targets
    the configured project and sends events to the URL specified in
    GERRIT_WEBHOOK_TARGET_URL.

    Returns:
        A standardized API response containing the webhook registration
        result or existing configuration.
    """
    result = GerritWatcher().register_webhook()
    return api_response(
        success=True,
        message="Gerrit Webhook registered successfully.",
        data=result,
        status_code=HTTPStatus.OK,
    )
