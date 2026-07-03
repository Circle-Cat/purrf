"""FastAPI routes for the recruiting blacklist admin page: list + unblock.

Kept separate from BoardController: the existing POST /recruiting/blacklist
route (BoardController.blacklist, the block action) stays there. This
controller owns the two admin-facing routes that read/clear org-wide block
state, unscoped to any application. Its GET /recruiting/blacklist route
shares a path with BoardController's POST route on the same path — FastAPI
dispatches by (path, method), so the two coexist fine as separate routers.
"""

from fastapi import APIRouter

from backend.common.fast_api_response_wrapper import api_response
from backend.common.permissions import Permission
from backend.utils.permission_decorators import authenticate
from backend.dto.user_context_dto import UserContextDto
from backend.common.api_endpoints import (
    RECRUITING_BLACKLIST_ENDPOINT,
    RECRUITING_BLACKLIST_UNBLOCK_ENDPOINT,
)


class BlacklistController:
    """Admin routes for viewing and clearing the org-wide user blacklist.

    Both routes are gated by ``Permission.RECRUITING_BLACKLIST_WRITE`` — the
    same permission that gates the block action itself in BoardController;
    there is no separate read permission.
    """

    def __init__(self, blacklist_service, database):
        """
        Args:
            blacklist_service (BlacklistService): List/unblock business logic.
            database: Async session provider.
        """
        self.blacklist_service = blacklist_service
        self.database = database
        self.router = APIRouter(tags=["recruiting-blacklist"])

        self.router.add_api_route(
            RECRUITING_BLACKLIST_ENDPOINT,
            endpoint=authenticate(permissions=[Permission.RECRUITING_BLACKLIST_WRITE])(
                self.list_blacklist
            ),
            methods=["GET"],
            response_model=None,
        )
        self.router.add_api_route(
            RECRUITING_BLACKLIST_UNBLOCK_ENDPOINT,
            endpoint=authenticate(permissions=[Permission.RECRUITING_BLACKLIST_WRITE])(
                self.unblock
            ),
            methods=["DELETE"],
            response_model=None,
        )

    async def list_blacklist(
        self, current_user: UserContextDto, search: str | None = None
    ):
        """List every currently-blocked user."""
        async with self.database.session() as session:
            result = await self.blacklist_service.list_blacklist(session, search)
        return api_response(message="Blacklist fetched.", data=result)

    async def unblock(self, current_user: UserContextDto, user_id: int):
        """Clear a user's block state."""
        async with self.database.session() as session:
            await self.blacklist_service.unblock(session, user_id)
        return api_response(message="User unblocked.")
