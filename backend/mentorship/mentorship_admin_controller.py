from fastapi import APIRouter, Depends
from backend.dto.participant_search_filter_dto import ParticipantSearchFilterDto
from backend.common.fast_api_response_wrapper import api_response
from backend.common.api_endpoints import (
    MENTORSHIP_ADMIN_PARTICIPANTS,
    MENTORSHIP_ADMIN_PAIRS_MEETINGS,
)
from backend.common.permissions import Permission
from backend.utils.permission_decorators import authenticate


class MentorshipAdminController:
    def __init__(self, mentorship_admin_service, database):
        self.mentorship_admin_service = mentorship_admin_service
        self.database = database
        self.router = APIRouter(tags=["mentorship-admin"])

        self.router.add_api_route(
            MENTORSHIP_ADMIN_PARTICIPANTS,
            endpoint=authenticate(permissions=[Permission.MENTORSHIP_PARTICIPANT_READ])(
                self.search_participants
            ),
            methods=["GET"],
            response_model=None,
        )

        self.router.add_api_route(
            MENTORSHIP_ADMIN_PAIRS_MEETINGS,
            endpoint=authenticate(permissions=[Permission.MENTORSHIP_PARTICIPANT_READ])(
                self.get_meeting_log
            ),
            methods=["GET"],
            response_model=None,
        )

    async def search_participants(
        self,
        filters: ParticipantSearchFilterDto = Depends(),
        limit: int = 100,
        offset: int = 0,
        sort_by: str | None = None,
        order: str = "asc",
    ):
        async with self.database.session() as session:
            result = await self.mentorship_admin_service.search_participants(
                session, filters, limit, offset, sort_by, order
            )
        return api_response(
            message="Successfully retrieved participant search results.",
            data=result,
        )

    async def get_meeting_log(self, pair_id: int):
        """
        Retrieve the meeting log for a mentorship pair.

        Args:
            pair_id (int): The mentorship pair ID.

        Returns:
            API response containing the meeting log, or None if the pair does
            not exist.
        """
        async with self.database.session() as session:
            result = await self.mentorship_admin_service.get_meeting_log(
                session, pair_id
            )
        return api_response(
            message="Successfully retrieved meeting log.",
            data=result,
        )
