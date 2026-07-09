from fastapi import APIRouter, File, UploadFile
from backend.common.fast_api_response_wrapper import api_response
from backend.utils.permission_decorators import authenticate
from backend.dto.user_context_dto import UserContextDto
from backend.dto.application_dto import ApplicationSubmitDto, ApplicationEditDto
from backend.common.api_endpoints import (
    RECRUITING_PUBLIC_JOB_ENDPOINT,
    RECRUITING_PUBLIC_JOBS_ENDPOINT,
    RECRUITING_RESUMES_ENDPOINT,
    RECRUITING_APPLICATIONS_ENDPOINT,
    RECRUITING_APPLICATION_ENDPOINT,
    RECRUITING_APPLICATIONS_MINE_ENDPOINT,
    RECRUITING_MY_APPLICATIONS_ENDPOINT,
)


class ApplicationController:
    """FastAPI routes for candidate application submission (login-gated)."""

    def __init__(self, application_service, job_service, resume_storage, database):
        """
        Args:
            application_service (ApplicationService): Submit/edit/get logic.
            job_service (JobService): Provides get_published_job.
            resume_storage (ResumeStorage): Content-addressed résumé upload.
            database: Async session provider.
        """
        self.application_service = application_service
        self.job_service = job_service
        self.resume_storage = resume_storage
        self.database = database
        self.router = APIRouter(tags=["recruiting-applications"])

        self.router.add_api_route(
            RECRUITING_APPLICATIONS_MINE_ENDPOINT,
            endpoint=authenticate()(self.get_my_application),
            methods=["GET"],
            response_model=None,
        )
        self.router.add_api_route(
            RECRUITING_MY_APPLICATIONS_ENDPOINT,
            endpoint=authenticate()(self.list_my_applications),
            methods=["GET"],
            response_model=None,
        )
        self.router.add_api_route(
            RECRUITING_PUBLIC_JOB_ENDPOINT,
            endpoint=authenticate()(self.get_public_job),
            methods=["GET"],
            response_model=None,
        )
        self.router.add_api_route(
            RECRUITING_PUBLIC_JOBS_ENDPOINT,
            endpoint=authenticate()(self.list_public_jobs),
            methods=["GET"],
            response_model=None,
        )
        self.router.add_api_route(
            RECRUITING_RESUMES_ENDPOINT,
            endpoint=authenticate()(self.upload_resume),
            methods=["POST"],
            response_model=None,
        )
        self.router.add_api_route(
            RECRUITING_APPLICATIONS_ENDPOINT,
            endpoint=authenticate()(self.submit_application),
            methods=["POST"],
            response_model=None,
        )
        self.router.add_api_route(
            RECRUITING_APPLICATION_ENDPOINT,
            endpoint=authenticate()(self.edit_application),
            methods=["PATCH"],
            response_model=None,
        )

    async def get_public_job(self, current_user: UserContextDto, job_id: int):
        """Fetch a published posting's candidate-safe projection for the application form."""
        async with self.database.session() as session:
            result = await self.job_service.get_published_job_public(session, job_id)
        return api_response(message="Job fetched.", data=result)

    async def list_public_jobs(self, current_user: UserContextDto):
        """List published postings as candidate-safe summaries for the browse page."""
        async with self.database.session() as session:
            result = await self.job_service.list_published(session)
        return api_response(message="Jobs fetched.", data=result)

    async def upload_resume(
        self, current_user: UserContextDto, file: UploadFile = File(...)
    ):
        """Store an uploaded résumé content-addressed and return its reference."""
        data = await file.read()
        sha256, object_key = self.resume_storage.put(data)
        return api_response(
            message="Resume stored.", data={"sha256": sha256, "objectKey": object_key}
        )

    async def submit_application(
        self, current_user: UserContextDto, submit_data: ApplicationSubmitDto
    ):
        """Submit an application; lands Applied (or Rejected for blocked users)."""
        async with self.database.session() as session:
            result = await self.application_service.submit(
                session, current_user, submit_data
            )
        return api_response(message="Application submitted.", data=result)

    async def edit_application(
        self,
        current_user: UserContextDto,
        application_id: int,
        edit_data: ApplicationEditDto,
    ):
        """Overwrite the caller's application while it is still Applied."""
        async with self.database.session() as session:
            result = await self.application_service.edit(
                session, current_user, application_id, edit_data
            )
        return api_response(message="Application updated.", data=result)

    async def get_my_application(self, current_user: UserContextDto, job_id: int):
        """Return the caller's application for a job (query param job_id)."""
        async with self.database.session() as session:
            result = await self.application_service.get_mine(
                session, current_user, job_id
            )
        return api_response(message="Application fetched.", data=result)

    async def list_my_applications(self, current_user: UserContextDto):
        """Return every application the caller has ever submitted, any job kind."""
        async with self.database.session() as session:
            result = await self.application_service.list_mine(session, current_user)
        return api_response(message="Applications fetched.", data=result)
