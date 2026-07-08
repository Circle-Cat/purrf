from fastapi import APIRouter, Response

from backend.common.fast_api_response_wrapper import api_response
from backend.common.permissions import Permission
from backend.utils.permission_decorators import authenticate
from backend.dto.board_dto import (
    BlacklistDto,
    CommentCreateDto,
    ReassignDto,
    RoundChangeDto,
    StageChangeDto,
    SubStatusChangeDto,
)
from backend.dto.user_context_dto import UserContextDto
from backend.common.api_endpoints import (
    RECRUITING_BOARD_JOBS_ENDPOINT,
    RECRUITING_JOB_BOARD_ENDPOINT,
    RECRUITING_APPLICATION_ENDPOINT,
    RECRUITING_APPLICATION_STAGE_ENDPOINT,
    RECRUITING_APPLICATION_SUB_STATUS_ENDPOINT,
    RECRUITING_APPLICATION_ASSIGNMENT_ENDPOINT,
    RECRUITING_APPLICATION_ROUND_ENDPOINT,
    RECRUITING_APPLICATION_RESUME_ENDPOINT,
    RECRUITING_APPLICATION_ACTIVITY_ENDPOINT,
    RECRUITING_APPLICATION_OTHER_APPLICATIONS_ENDPOINT,
    RECRUITING_APPLICATION_COMMENTS_ENDPOINT,
    RECRUITING_BLACKLIST_ENDPOINT,
)


class BoardController:
    """FastAPI routes for the owner-facing recruiting application board.

    The read routes (including the résumé proxy download) are plain
    login-gated (``authenticate()``) rather than permission-gated: ownership
    is a row-level check performed by ``BoardService`` against a job's
    configured owner ids, not an enum permission. The decision routes
    (stage/sub-status/reassign/round) are double-gated:
    ``Permission.RECRUITING_APPLICATION_ADVANCE`` at the route, and the same
    row-level owner check in ``BoardService``. The blacklist route is
    permission-gated only (``Permission.RECRUITING_BLACKLIST_WRITE``):
    ``BoardService.blacklist`` deliberately performs no job-ownership check,
    since it's an org-level sanction rather than a per-posting decision.

    The comments routes (list/add) are also plain login-gated: like the
    reads above, access is a row-level owner-or-current-assignee check
    inside ``BoardService`` -- unlike the other write routes, posting a
    comment carries no enum permission gate, since anyone who can already
    view the application may also discuss it.
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
            RECRUITING_APPLICATION_ENDPOINT,
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
            RECRUITING_APPLICATION_ACTIVITY_ENDPOINT,
            endpoint=authenticate()(self.get_application_activity),
            methods=["GET"],
            response_model=None,
        )
        self.router.add_api_route(
            RECRUITING_APPLICATION_OTHER_APPLICATIONS_ENDPOINT,
            endpoint=authenticate()(self.get_other_applications),
            methods=["GET"],
            response_model=None,
        )
        self.router.add_api_route(
            RECRUITING_APPLICATION_COMMENTS_ENDPOINT,
            endpoint=authenticate()(self.list_comments),
            methods=["GET"],
            response_model=None,
        )
        self.router.add_api_route(
            RECRUITING_APPLICATION_COMMENTS_ENDPOINT,
            endpoint=authenticate()(self.add_comment),
            methods=["POST"],
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
            RECRUITING_APPLICATION_ASSIGNMENT_ENDPOINT,
            endpoint=authenticate(
                permissions=[Permission.RECRUITING_APPLICATION_ADVANCE]
            )(self.reassign),
            methods=["PATCH"],
            response_model=None,
        )
        self.router.add_api_route(
            RECRUITING_APPLICATION_ROUND_ENDPOINT,
            endpoint=authenticate(
                permissions=[Permission.RECRUITING_APPLICATION_ADVANCE]
            )(self.set_round),
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

    async def get_application_activity(
        self, current_user: UserContextDto, application_id: int
    ):
        """Return an application's owner-facing audit timeline, newest first."""
        async with self.database.session() as session:
            result = await self.board_service.get_application_activity(
                session, current_user, application_id
            )
        return api_response(message="Application activity fetched.", data=result)

    async def get_other_applications(
        self, current_user: UserContextDto, application_id: int
    ):
        """Return a candidate's other applications, for the cross-posting
        aggregation view on the shared application detail page."""
        async with self.database.session() as session:
            result = await self.board_service.get_other_applications(
                session, current_user, application_id
            )
        return api_response(message="Other applications fetched.", data=result)

    async def list_comments(self, current_user: UserContextDto, application_id: int):
        """Return every comment on an application, newest first."""
        async with self.database.session() as session:
            result = await self.board_service.list_comments(
                session, current_user, application_id
            )
        return api_response(message="Comments fetched.", data=result)

    async def add_comment(
        self,
        current_user: UserContextDto,
        application_id: int,
        comment_data: CommentCreateDto,
    ):
        """Post a comment on an application."""
        async with self.database.session() as session:
            result = await self.board_service.add_comment(
                session, current_user, application_id, comment_data
            )
        return api_response(message="Comment posted.", data=result)

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

    async def reassign(
        self,
        current_user: UserContextDto,
        application_id: int,
        reassign_data: ReassignDto,
    ):
        """Change who is responsible for an application's current stage."""
        async with self.database.session() as session:
            result = await self.board_service.reassign(
                session, current_user, application_id, reassign_data
            )
        return api_response(message="Application reassigned.", data=result)

    async def set_round(
        self,
        current_user: UserContextDto,
        application_id: int,
        round_data: RoundChangeDto,
    ):
        """Manually advance an application to a round within its current stage."""
        async with self.database.session() as session:
            result = await self.board_service.set_round(
                session, current_user, application_id, round_data
            )
        return api_response(message="Application round updated.", data=result)

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
