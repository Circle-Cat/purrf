from fastapi import APIRouter

from backend.common.api_endpoints import (
    GUIDE_PROGRESS_ENDPOINT,
    GUIDES_PROGRESS_ENDPOINT,
)
from backend.common.fast_api_response_wrapper import api_response
from backend.dto.guide_progress_dto import GuideProgressUpdateDto
from backend.dto.user_context_dto import UserContextDto
from backend.utils.permission_decorators import authenticate


class GuideProgressController:
    """FastAPI routes for the caller's own onboarding guide progress.

    Plain login-gated (authenticate()): both routes act on
    current_user.user_id only, so there is no other user's data to gate.
    """

    def __init__(self, guide_progress_service, database):
        """
        Args:
            guide_progress_service (GuideProgressService): Guide progress rules.
            database: Async session provider.
        """
        self.guide_progress_service = guide_progress_service
        self.database = database
        self.router = APIRouter(tags=["onboarding-guides"])

        self.router.add_api_route(
            GUIDES_PROGRESS_ENDPOINT,
            endpoint=authenticate()(self.list_progress),
            methods=["GET"],
            response_model=None,
        )
        self.router.add_api_route(
            GUIDE_PROGRESS_ENDPOINT,
            endpoint=authenticate()(self.record_progress),
            methods=["PUT"],
            response_model=None,
        )

    async def list_progress(self, current_user: UserContextDto):
        """List the caller's progress on every guide they have a record for."""
        async with self.database.session() as session:
            result = await self.guide_progress_service.list_for_user(
                session, current_user.user_id
            )
        return api_response(message="Guide progress fetched.", data=result)

    async def record_progress(
        self,
        guide_key: str,
        body: GuideProgressUpdateDto,
        current_user: UserContextDto,
    ):
        """Record that the caller completed, dismissed or snoozed one guide."""
        async with self.database.session() as session:
            result = await self.guide_progress_service.record(
                session, current_user.user_id, guide_key, body.status
            )
        return api_response(message="Guide progress saved.", data=result)
