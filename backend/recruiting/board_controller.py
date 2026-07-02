from fastapi import APIRouter

from backend.common.fast_api_response_wrapper import api_response
from backend.utils.permission_decorators import authenticate
from backend.dto.user_context_dto import UserContextDto
from backend.common.api_endpoints import (
    RECRUITING_BOARD_JOBS_ENDPOINT,
    RECRUITING_JOB_BOARD_ENDPOINT,
    RECRUITING_APPLICATION_DETAIL_ENDPOINT,
)


class BoardController:
    """FastAPI routes for the owner-facing recruiting application board.

    All routes are plain login-gated (``authenticate()``) rather than
    permission-gated: ownership is a row-level check performed by
    ``BoardService`` against a job's configured owner ids, not an enum
    permission.
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
