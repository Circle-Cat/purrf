from fastapi import APIRouter

from backend.common.api_endpoints import (
    RECRUITING_NOTIFICATIONS_ENDPOINT,
    RECRUITING_NOTIFICATIONS_READ_ENDPOINT,
    RECRUITING_NOTIFICATION_ENDPOINT,
)
from backend.common.fast_api_response_wrapper import api_response
from backend.dto.notification_dto import MarkNotificationsReadDto
from backend.dto.user_context_dto import UserContextDto
from backend.utils.permission_decorators import authenticate


class RecruitingNotificationController:
    """FastAPI routes for the caller's own in-app notifications.

    Notifications are light reminders. Opening the bell marks what it shows
    read (POST read), which keeps the rows listed; dismissing takes them off
    the bell (DELETE-one, DELETE-all). Every route is plain login-gated
    (authenticate()): every query is already scoped to current_user.user_id
    inside the service, so there's no cross-user access to gate with a
    Permission enum.
    """

    def __init__(self, notification_service, database):
        """
        Args:
            notification_service (RecruitingNotificationService): List/dismiss logic.
            database: Async session provider.
        """
        self.notification_service = notification_service
        self.database = database
        self.router = APIRouter(tags=["recruiting-notifications"])

        self.router.add_api_route(
            RECRUITING_NOTIFICATIONS_ENDPOINT,
            endpoint=authenticate()(self.list_notifications),
            methods=["GET"],
            response_model=None,
        )
        # Ahead of the {notification_id} route, so "read" is never taken for
        # an id.
        self.router.add_api_route(
            RECRUITING_NOTIFICATIONS_READ_ENDPOINT,
            endpoint=authenticate()(self.mark_read),
            methods=["POST"],
            response_model=None,
        )
        self.router.add_api_route(
            RECRUITING_NOTIFICATION_ENDPOINT,
            endpoint=authenticate()(self.dismiss),
            methods=["DELETE"],
            response_model=None,
        )
        self.router.add_api_route(
            RECRUITING_NOTIFICATIONS_ENDPOINT,
            endpoint=authenticate()(self.dismiss_all),
            methods=["DELETE"],
            response_model=None,
        )

    async def list_notifications(
        self, current_user: UserContextDto, limit: int = 20, offset: int = 0
    ):
        """List the caller's notifications (newest first) plus unread count."""
        async with self.database.session() as session:
            result = await self.notification_service.list_for_user(
                session, current_user.user_id, limit=limit, offset=offset
            )
        return api_response(message="Notifications fetched.", data=result)

    async def mark_read(
        self, current_user: UserContextDto, body: MarkNotificationsReadDto
    ):
        """Mark the notifications the bell showed read."""
        async with self.database.session() as session:
            result = await self.notification_service.mark_read(
                session, current_user.user_id, body.ids
            )
        return api_response(message="Notifications marked read.", data=result)

    async def dismiss(self, current_user: UserContextDto, notification_id: int):
        """Take one of the caller's notifications off the bell."""
        async with self.database.session() as session:
            result = await self.notification_service.dismiss(
                session, current_user.user_id, notification_id
            )
        return api_response(message="Notification dismissed.", data=result)

    async def dismiss_all(self, current_user: UserContextDto):
        """Take every one of the caller's notifications off the bell."""
        async with self.database.session() as session:
            result = await self.notification_service.dismiss_all(
                session, current_user.user_id
            )
        return api_response(message="All notifications dismissed.", data=result)
