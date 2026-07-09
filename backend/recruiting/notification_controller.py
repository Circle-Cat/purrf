from fastapi import APIRouter

from backend.common.api_endpoints import (
    RECRUITING_NOTIFICATIONS_ENDPOINT,
    RECRUITING_NOTIFICATION_READ_ENDPOINT,
    RECRUITING_NOTIFICATIONS_READ_ALL_ENDPOINT,
)
from backend.common.fast_api_response_wrapper import api_response
from backend.dto.user_context_dto import UserContextDto
from backend.utils.permission_decorators import authenticate


class RecruitingNotificationController:
    """FastAPI routes for the caller's own in-app notifications.

    All three routes are plain login-gated (authenticate()): every query
    is already scoped to current_user.user_id inside the service, so
    there's no cross-user access to gate with a Permission enum.
    """

    def __init__(self, notification_service, database):
        """
        Args:
            notification_service (RecruitingNotificationService): List/mark-read logic.
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
        self.router.add_api_route(
            RECRUITING_NOTIFICATION_READ_ENDPOINT,
            endpoint=authenticate()(self.mark_read),
            methods=["POST"],
            response_model=None,
        )
        self.router.add_api_route(
            RECRUITING_NOTIFICATIONS_READ_ALL_ENDPOINT,
            endpoint=authenticate()(self.mark_all_read),
            methods=["POST"],
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

    async def mark_read(self, current_user: UserContextDto, notification_id: int):
        """Mark one of the caller's notifications read."""
        async with self.database.session() as session:
            result = await self.notification_service.mark_read(
                session, current_user.user_id, notification_id
            )
        return api_response(message="Notification marked read.", data=result)

    async def mark_all_read(self, current_user: UserContextDto):
        """Mark every one of the caller's unread notifications read."""
        async with self.database.session() as session:
            result = await self.notification_service.mark_all_read(
                session, current_user.user_id
            )
        return api_response(message="All notifications marked read.", data=result)
