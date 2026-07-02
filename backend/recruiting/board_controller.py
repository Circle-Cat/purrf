from fastapi import APIRouter, Response

from backend.common.fast_api_response_wrapper import api_response
from backend.common.permissions import Permission
from backend.utils.permission_decorators import authenticate
from backend.dto.board_dto import BlacklistDto, StageChangeDto, SubStatusChangeDto
from backend.dto.user_context_dto import UserContextDto
from backend.common.api_endpoints import (
    RECRUITING_BOARD_JOBS_ENDPOINT,
    RECRUITING_JOB_BOARD_ENDPOINT,
    RECRUITING_APPLICATION_DETAIL_ENDPOINT,
    RECRUITING_APPLICATION_STAGE_ENDPOINT,
    RECRUITING_APPLICATION_SUB_STATUS_ENDPOINT,
    RECRUITING_APPLICATION_RESUME_ENDPOINT,
    RECRUITING_BLACKLIST_ENDPOINT,
)


class BoardController:
    """FastAPI routes for the owner-facing recruiting application board.

    The read routes (including the résumé proxy download) are plain
    login-gated (``authenticate()``) rather than permission-gated: ownership
    is a row-level check performed by ``BoardService`` against a job's
    configured owner ids, not an enum permission. The two decision routes
    (stage/sub-status) are double-gated:
    ``Permission.RECRUITING_APPLICATION_ADVANCE`` at the route, and the same
    row-level owner check in ``BoardService``. The blacklist route is
    permission-gated only (``Permission.RECRUITING_BLACKLIST_WRITE``):
    ``BoardService.blacklist`` deliberately performs no job-ownership check,
    since it's an org-level sanction rather than a per-posting decision.
    """

    def __init__(self, board_service, database):
        """
        Args:
            board_service (BoardService): Board read logic (job switcher,
                pipeline, applicant detail).
            database: Async session provider.
        """
        self.board_service = board_service
        self.database = database
        self.router = APIRouter(tags=["recruiting-board"])

        self.router.add_api_route(
            RECRUITING_BOARD_JOBS_ENDPOINT,
            endpoint=authenticate()(self.list_my_jobs),
            methods=["GET"],
            response_model=None,
        )
        self.router.add_api_route(
            RECRUITING_JOB_BOARD_ENDPOINT,
            endpoint=authenticate()(self.get_board),
            methods=["GET"],
            response_model=None,
        )
        self.router.add_api_route(
            RECRUITING_APPLICATION_DETAIL_ENDPOINT,
            endpoint=authenticate()(self.get_application_detail),
            methods=["GET"],
            response_model=None,
        )
        self.router.add_api_route(
            RECRUITING_APPLICATION_RESUME_ENDPOINT,
            endpoint=authenticate()(self.get_resume),
            methods=["GET"],
            response_model=None,
        )
        self.router.add_api_route(
            RECRUITING_APPLICATION_STAGE_ENDPOINT,
            endpoint=authenticate(
                permissions=[Permission.RECRUITING_APPLICATION_ADVANCE]
            )(self.change_stage),
            methods=["PATCH"],
            response_model=None,
        )
        self.router.add_api_route(
            RECRUITING_APPLICATION_SUB_STATUS_ENDPOINT,
            endpoint=authenticate(
                permissions=[Permission.RECRUITING_APPLICATION_ADVANCE]
            )(self.set_sub_status),
            methods=["PATCH"],
            response_model=None,
        )
        self.router.add_api_route(
            RECRUITING_BLACKLIST_ENDPOINT,
            endpoint=authenticate(permissions=[Permission.RECRUITING_BLACKLIST_WRITE])(
                self.blacklist
            ),
            methods=["POST"],
            response_model=None,
        )

    async def list_my_jobs(self, current_user: UserContextDto):
        """List jobs the caller owns, for the board's job switcher."""
        async with self.database.session() as session:
            result = await self.board_service.list_my_jobs(session, current_user)
        return api_response(message="Jobs fetched.", data=result)

    async def get_board(self, current_user: UserContextDto, job_id: int):
        """Return a job's applications grouped by stage, for the board columns."""
        async with self.database.session() as session:
            result = await self.board_service.get_board(session, current_user, job_id)
        return api_response(message="Board fetched.", data=result)

    async def get_application_detail(
        self, current_user: UserContextDto, application_id: int
    ):
        """Return the owner-facing full view of one application."""
        async with self.database.session() as session:
            result = await self.board_service.get_application_detail(
                session, current_user, application_id
            )
        return api_response(message="Application fetched.", data=result)

    async def get_resume(self, current_user: UserContextDto, application_id: int):
        """Proxy-download an application's résumé PDF.

        Deliberately returns a raw ``fastapi.Response`` rather than going
        through ``api_response``: the body is binary PDF bytes, not JSON, so
        the usual ``{message, data}`` envelope doesn't apply here.
        """
        async with self.database.session() as session:
            data = await self.board_service.get_resume(
                session, current_user, application_id
            )
        return Response(content=data, media_type="application/pdf")

    async def change_stage(
        self,
        current_user: UserContextDto,
        application_id: int,
        stage_data: StageChangeDto,
    ):
        """Advance or reject an application to a new pipeline stage."""
        async with self.database.session() as session:
            result = await self.board_service.change_stage(
                session, current_user, application_id, stage_data
            )
        return api_response(message="Application stage updated.", data=result)

    async def set_sub_status(
        self,
        current_user: UserContextDto,
        application_id: int,
        sub_status_data: SubStatusChangeDto,
    ):
        """Manually switch an application's sub_status within its stage."""
        async with self.database.session() as session:
            result = await self.board_service.set_sub_status(
                session, current_user, application_id, sub_status_data
            )
        return api_response(message="Application sub-status updated.", data=result)

    async def blacklist(
        self,
        current_user: UserContextDto,
        blacklist_data: BlacklistDto,
    ):
        """Block a user org-wide and close out the triggering application."""
        async with self.database.session() as session:
            result = await self.board_service.blacklist(
                session, current_user, blacklist_data
            )
        return api_response(message="User blacklisted.", data=result)
