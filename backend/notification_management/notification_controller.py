from http import HTTPStatus
from fastapi import APIRouter
from pydantic import BaseModel
from backend.common.fast_api_response_wrapper import api_response
from backend.common.constants import SINGLE_GOOGLE_CHAT_EVENT_TYPES
from backend.common.user_role import UserRole
from backend.common.api_endpoints import (
    GOOGLE_CHAT_SUBSCRIBE_ENDPOINT,
    MICROSOFT_CHAT_SUBSCRIBE_ENDPOINT,
)
from backend.utils.permission_decorators import authenticate


class MicrosoftChatSubscribeRequest(BaseModel):
    chat_id: str
    notification_url: str
    lifecycle_notification_url: str


class GoogleChatSpaceSubscribeRequest(BaseModel):
    project_id: str
    topic_id: str
    space_id: str


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
        """
        if not microsoft_chat_subscription_service:
            raise ValueError("MicrosoftChatSubscriptionService instances is required.")
        if not google_chat_subscription_service:
            raise ValueError("GoogleChatSubscriptionService instances is required.")

        self.microsoft_chat_subscription_service = microsoft_chat_subscription_service
        self.google_chat_subscription_service = google_chat_subscription_service

        self.router = APIRouter(tags=["notification"])

        self.router.add_api_route(
            MICROSOFT_CHAT_SUBSCRIBE_ENDPOINT,
            endpoint=authenticate(roles=[UserRole.ADMIN])(
                self.subscribe_microsoft_chat_messages
            ),
            methods=["POST"],
            response_model=dict,
        )
        self.router.add_api_route(
            GOOGLE_CHAT_SUBSCRIBE_ENDPOINT,
            endpoint=authenticate(roles=[UserRole.ADMIN])(
                self.subscribe_google_chat_space
            ),
            methods=["POST"],
            response_model=dict,
        )

    async def subscribe_microsoft_chat_messages(
        self, request_body: MicrosoftChatSubscribeRequest, current_user: str
    ):
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
        (
            message,
            data,
        ) = await self.microsoft_chat_subscription_service.subscribe_chat_messages(
            request_body.chat_id,
            request_body.notification_url,
            request_body.lifecycle_notification_url,
        )
        return api_response(
            success=True,
            message=message,
            data=data,
            status_code=HTTPStatus.CREATED,
        )

    async def subscribe_google_chat_space(
        self, request_body: GoogleChatSpaceSubscribeRequest
    ):
        """
        API endpoint to subscribe to chat space events.
        """

        response = (
            self.google_chat_subscription_service.create_workspaces_subscriptions(
                project_id=request_body.project_id,
                topic_id=request_body.topic_id,
                space_id=request_body.space_id,
                event_types=SINGLE_GOOGLE_CHAT_EVENT_TYPES,
            )
        )
        return api_response(
            success=True,
            message=f"Successfully created Google Chat space {request_body.space_id} subscription",
            data=response,
            status_code=HTTPStatus.CREATED,
        )
