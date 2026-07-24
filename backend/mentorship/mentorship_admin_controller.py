from typing import Literal
from datetime import datetime
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from backend.dto.participant_search_filter_dto import ParticipantSearchFilterDto
from backend.common.fast_api_response_wrapper import api_response
from backend.common.api_endpoints import (
    MENTORSHIP_ADMIN_PARTICIPANTS,
    MENTORSHIP_ADMIN_PARTICIPANTS_EXPORT,
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
            endpoint=authenticate(permissions=[Permission.MENTORSHIP_ADMIN_READ])(
                self.search_participants
            ),
            methods=["GET"],
            response_model=None,
        )

        self.router.add_api_route(
            MENTORSHIP_ADMIN_PAIRS_MEETINGS,
            endpoint=authenticate(permissions=[Permission.MENTORSHIP_ADMIN_READ])(
                self.get_meeting_log
            ),
            methods=["GET"],
            response_model=None,
        )

        self.router.add_api_route(
            MENTORSHIP_ADMIN_PARTICIPANTS_EXPORT,
            endpoint=authenticate(permissions=[Permission.MENTORSHIP_ADMIN_READ])(
                self.export_participants
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
        """
        Search mentorship participants and non-participants.

        Args:
            filters (ParticipantSearchFilterDto): Search filters.
            limit (int): Maximum number of rows to return.
            offset (int): Pagination offset.
            sort_by (str | None): Column to sort by.
            order (str): Sort direction ("asc" or "desc").

        Returns:
            API response containing matching participant records.
        """
        async with self.database.session() as session:
            result = await self.mentorship_admin_service.search_participants(
                session, filters, limit, offset, sort_by, order
            )
        return api_response(
            message="Successfully retrieved participant search results.",
            data=result,
        )

    async def export_participants(
        self,
        filters: ParticipantSearchFilterDto = Depends(),
        mode: Literal["summary", "detailed"] | None = None,
    ):
        """
        Stream the participant search results as a downloadable CSV.

        Args:
            filters (ParticipantSearchFilterDto): Search filters used for
                the export. filters.participation_status must be set.
            mode (Literal["summary", "detailed"] | None): "summary" (one row
                per participant record) or "detailed" (one row per meeting).
                Required for a participant export. Ignored for a
                non-participant export.

        Returns:
            StreamingResponse: Streaming CSV file response.
        """
        today = datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d")
        if filters.participation_status == "participant" and mode:
            filename = f"{filters.participation_status}_{mode}_{today}.csv"
        else:
            filename = f"{filters.participation_status}_{today}.csv"
        return StreamingResponse(
            self.mentorship_admin_service.stream_export_csv(filters, mode),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
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
