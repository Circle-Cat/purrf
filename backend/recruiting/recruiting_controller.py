from datetime import datetime, timezone
from fastapi import APIRouter
from backend.common.fast_api_response_wrapper import api_response
from backend.utils.permission_decorators import authenticate
from backend.common.permissions import Permission
from backend.common.recruiting_enums import ApplicationStage
from backend.dto.user_context_dto import UserContextDto
from backend.dto.job_dto import JobCreateDto
from backend.dto.application_dto import ApplicationSubmitDto
from backend.common.api_endpoints import (
    RECRUITING_JOBS_ENDPOINT,
    RECRUITING_JOB_ENDPOINT,
    RECRUITING_JOB_PUBLISH_ENDPOINT,
    RECRUITING_JOB_CLOSE_ENDPOINT,
    RECRUITING_JOB_APPLY_ENDPOINT,
    RECRUITING_JOB_BOARD_ENDPOINT,
    RECRUITING_APPLICATION_VIEW_ENDPOINT,
    RECRUITING_APPLICATION_ADVANCE_ENDPOINT,
)


class RecruitingController:
    """FastAPI routes for the recruiting MVP."""

    def __init__(self, job_service, application_service, database):
        """
        Initialize the RecruitingController with required dependencies and register routes.

        Args:
            job_service: JobService instance for posting lifecycle operations.
            application_service: ApplicationService instance for screening operations.
            database: Database access object providing async session management.
        """
        self.job_service = job_service
        self.application_service = application_service
        self.database = database
        self.router = APIRouter(tags=["recruiting"])

        self.router.add_api_route(
            RECRUITING_JOBS_ENDPOINT,
            endpoint=authenticate(permissions=[Permission.RECRUITING_JOB_WRITE])(
                self.create_job
            ),
            methods=["POST"],
            response_model=None,
        )
        self.router.add_api_route(
            RECRUITING_JOBS_ENDPOINT,
            endpoint=authenticate(permissions=[Permission.RECRUITING_JOB_READ])(
                self.list_jobs
            ),
            methods=["GET"],
            response_model=None,
        )
        self.router.add_api_route(
            RECRUITING_JOB_ENDPOINT,
            endpoint=authenticate(permissions=[Permission.RECRUITING_JOB_WRITE])(
                self.update_job
            ),
            methods=["PUT"],
            response_model=None,
        )
        self.router.add_api_route(
            RECRUITING_JOB_PUBLISH_ENDPOINT,
            endpoint=authenticate(permissions=[Permission.RECRUITING_JOB_WRITE])(
                self.publish_job
            ),
            methods=["POST"],
            response_model=None,
        )
        self.router.add_api_route(
            RECRUITING_JOB_CLOSE_ENDPOINT,
            endpoint=authenticate(permissions=[Permission.RECRUITING_JOB_WRITE])(
                self.close_job
            ),
            methods=["POST"],
            response_model=None,
        )
        self.router.add_api_route(
            RECRUITING_JOB_ENDPOINT,
            endpoint=authenticate()(self.get_job),
            methods=["GET"],
            response_model=None,
        )
        self.router.add_api_route(
            RECRUITING_JOB_APPLY_ENDPOINT,
            endpoint=authenticate()(self.submit_application),
            methods=["POST"],
            response_model=None,
        )
        self.router.add_api_route(
            RECRUITING_JOB_BOARD_ENDPOINT,
            endpoint=authenticate(permissions=[Permission.RECRUITING_APPLICATION_READ])(
                self.get_board
            ),
            methods=["GET"],
            response_model=None,
        )
        self.router.add_api_route(
            RECRUITING_APPLICATION_VIEW_ENDPOINT,
            endpoint=authenticate(permissions=[Permission.RECRUITING_APPLICATION_READ])(
                self.view_application
            ),
            methods=["POST"],
            response_model=None,
        )
        self.router.add_api_route(
            RECRUITING_APPLICATION_ADVANCE_ENDPOINT,
            endpoint=authenticate(permissions=[Permission.RECRUITING_APPLICATION_ADVANCE])(
                self.advance_application
            ),
            methods=["POST"],
            response_model=None,
        )

    async def create_job(self, current_user: UserContextDto, job_data: JobCreateDto):
        """Create a DRAFT posting."""
        async with self.database.session() as session:
            result = await self.job_service.create_job(session, job_data)
        return api_response(message="Job created.", data=result)

    async def list_jobs(self, current_user: UserContextDto):
        """List PUBLISHED postings."""
        async with self.database.session() as session:
            result = await self.job_service.list_published(session)
        return api_response(message="Jobs fetched.", data=result)

    async def update_job(
        self, current_user: UserContextDto, job_id: int, job_data: JobCreateDto
    ):
        """Update a posting (incl. form schema)."""
        async with self.database.session() as session:
            result = await self.job_service.update_job(session, job_id, job_data)
        return api_response(message="Job updated.", data=result)

    async def publish_job(self, current_user: UserContextDto, job_id: int):
        """Publish a posting."""
        async with self.database.session() as session:
            result = await self.job_service.publish_job(session, job_id)
        return api_response(message="Job published.", data=result)

    async def close_job(self, current_user: UserContextDto, job_id: int):
        """Close a posting."""
        async with self.database.session() as session:
            result = await self.job_service.close_job(session, job_id)
        return api_response(message="Job closed.", data=result)

    async def get_job(self, current_user: UserContextDto, job_id: int):
        """Fetch one posting (candidate-facing via direct link)."""
        async with self.database.session() as session:
            result = await self.job_service.get_job(session, job_id)
        return api_response(message="Job fetched.", data=result)

    async def submit_application(
        self,
        current_user: UserContextDto,
        job_id: int,
        submission: ApplicationSubmitDto,
    ):
        """Submit an application as the current candidate."""
        now = datetime.now(timezone.utc)
        async with self.database.session() as session:
            result = await self.application_service.submit(
                session, job_id, current_user.user_id, submission, now
            )
        return api_response(message="Application submitted.", data=result)

    async def get_board(self, current_user: UserContextDto, job_id: int):
        """List a posting's screening board."""
        now = datetime.now(timezone.utc)
        async with self.database.session() as session:
            result = await self.application_service.list_board(session, job_id, now)
        return api_response(message="Board fetched.", data=result)

    async def view_application(self, current_user: UserContextDto, application_id: int):
        """Record first screener view (locks + snapshots)."""
        async with self.database.session() as session:
            result = await self.application_service.mark_viewed(session, application_id)
        return api_response(message="Application viewed.", data=result)

    async def advance_application(
        self,
        current_user: UserContextDto,
        application_id: int,
        target_stage: ApplicationStage,
    ):
        """Manually advance an application to HIRED or REJECTED."""
        now = datetime.now(timezone.utc)
        async with self.database.session() as session:
            result = await self.application_service.advance(
                session, application_id, target_stage, now
            )
        return api_response(message="Application advanced.", data=result)
