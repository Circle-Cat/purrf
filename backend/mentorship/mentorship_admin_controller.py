from fastapi import APIRouter, Depends
from backend.dto.participant_search_filter_dto import ParticipantSearchFilterDto
from backend.common.fast_api_response_wrapper import api_response
from backend.common.api_endpoints import MENTORSHIP_ADMIN_PARTICIPANTS
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

    async def search_participants(
        self,
        filters: ParticipantSearchFilterDto = Depends(),
        limit: int = 100,
        offset: int = 0,
    ):
        async with self.database.session() as session:
            result = await self.mentorship_admin_service.search_participants(
                session, filters, limit, offset
            )
        return api_response(
            message="Successfully retrieved participant search results.",
            data=result,
        )
