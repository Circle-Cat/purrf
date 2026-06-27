from fastapi import APIRouter
from backend.common.fast_api_response_wrapper import api_response
from backend.utils.permission_decorators import authenticate
from backend.common.permissions import Permission
from backend.dto.user_context_dto import UserContextDto
from backend.dto.job_dto import JobCreateDto
from backend.common.api_endpoints import (
    RECRUITING_JOBS_ENDPOINT,
    RECRUITING_JOB_ENDPOINT,
    RECRUITING_JOB_PUBLISH_ENDPOINT,
    RECRUITING_JOB_CLOSE_ENDPOINT,
)


class RecruitingController:
    """FastAPI routes for recruiting job postings (publishing side)."""

    def __init__(self, job_service, database):
        """
        Initialize the RecruitingController and register job routes.

        Args:
            job_service: JobService instance for posting lifecycle operations.
            database: Database access object providing async session management.
        """
        self.job_service = job_service
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

    async def create_job(self, current_user: UserContextDto, job_data: JobCreateDto):
        """Create a DRAFT posting."""
        async with self.database.session() as session:
            result = await self.job_service.create_job(session, job_data)
        return api_response(message="Job created.", data=result)

    async def list_jobs(self, current_user: UserContextDto):
        """List postings."""
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
        """Fetch one posting."""
        async with self.database.session() as session:
            result = await self.job_service.get_job(session, job_id)
        return api_response(message="Job fetched.", data=result)
