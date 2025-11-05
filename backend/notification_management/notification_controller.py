from http import HTTPStatus
from flask import Blueprint, request
from backend.common.api_response_wrapper import api_response
from backend.common.constants import SINGLE_GOOGLE_CHAT_EVENT_TYPES

notification_bp = Blueprint("notification", __name__, url_prefix="/api")


class NotificationController:
    def __init__(
        self,
        microsoft_chat_subscription_service,
        google_chat_subscription_service,
    ):
        """
        Initialize the NotificationController with required dependencies.

        Args:
            microsoft_chat_subscription_service: MicrosoftChatSubscriptionService instance.
            google_chat_subscription_service: GoogleChatSubscriptionService instance.
            gerrit_subscription_service: GerritSubscriptionService instance.
        """
        if not microsoft_chat_subscription_service:
            raise ValueError("MicrosoftChatSubscriptionService instances is required.")
        if not google_chat_subscription_service:
            raise ValueError("GoogleChatSubscriptionService instances is required.")

        self.microsoft_chat_subscription_service = microsoft_chat_subscription_service
        self.google_chat_subscription_service = google_chat_subscription_service

    def register_routes(self, blueprint):
        """
        Register all historical data backfill routes to the given Flask blueprint.

        Args:
            blueprint: Flask Blueprint object to register routes on.
        """
        blueprint.add_url_rule(
            "/microsoft/chat/subscribe",
            view_func=self.subscribe_microsoft_chat_messages,
            methods=["POST"],
        )
        blueprint.add_url_rule(
            "/google/chat/spaces/subscribe",
            view_func=self.subscribe_google_chat_space,
            methods=["POST"],
        )

    async def subscribe_microsoft_chat_messages(self):
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

        (
            message,
            data,
        ) = await self.microsoft_chat_subscription_service.subscribe_chat_messages(
            chat_id, notification_url, lifecycle_notification_url
        )
        return api_response(
            success=True,
            message=message,
            data=data,
            status_code=HTTPStatus.CREATED,
        )

    def subscribe_google_chat_space(self):
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
        event_types = SINGLE_GOOGLE_CHAT_EVENT_TYPES

        response = (
            self.google_chat_subscription_service.create_workspaces_subscriptions(
                project_id=project_id,
                topic_id=topic_id,
                space_id=space_id,
                event_types=event_types,
            )
        )
        return api_response(
            success=True,
            message=response,
            status_code=HTTPStatus.CREATED,
        )
