from fastapi import APIRouter
from backend.common.fast_api_response_wrapper import api_response
from backend.utils.permission_decorators import authenticate
from backend.common.permissions import Permission
from backend.dto.user_context_dto import UserContextDto
from backend.dto.job_dto import JobCreateDto
from backend.dto.job_review_dto import JobReviewDecisionDto, JobSubmitDto
from backend.common.api_endpoints import (
    RECRUITING_JOBS_ENDPOINT,
    RECRUITING_JOB_ENDPOINT,
    RECRUITING_JOB_SUBMIT_ENDPOINT,
    RECRUITING_JOB_REQUEST_CLOSE_ENDPOINT,
    RECRUITING_JOB_REQUEST_REOPEN_ENDPOINT,
    RECRUITING_JOB_DISCARD_PENDING_EDIT_ENDPOINT,
    RECRUITING_JOB_ACTIVITY_ENDPOINT,
    RECRUITING_APPROVERS_ENDPOINT,
    RECRUITING_REVIEWS_ENDPOINT,
    RECRUITING_REVIEW_ENDPOINT,
    RECRUITING_INTERVIEW_POOL_ENDPOINT,
    RECRUITING_JOB_OWNERS_ENDPOINT,
    RECRUITING_EMAIL_SYNC_ENDPOINT,
    RECRUITING_EMAIL_SYNC_RECENT_ENDPOINT,
)


class RecruitingController:
    """FastAPI routes for recruiting job postings (publishing side), plus the two
    scheduled candidate-email syncs the CronJobs call — a nightly delta and a
    weekly reconcile."""

    def __init__(self, job_service, email_sync_service, database):
        """
        Initialize the RecruitingController and register its routes.

        Args:
            job_service: JobService instance for posting lifecycle operations.
            email_sync_service: EmailSyncService for the scheduled email sweep.
            database: Database access object providing async session management.
        """
        self.job_service = job_service
        self.email_sync_service = email_sync_service
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
            endpoint=authenticate(
                permissions=[
                    Permission.RECRUITING_JOB_READ,
                    Permission.RECRUITING_JOB_WRITE,
                    Permission.RECRUITING_JOB_APPROVE,
                    Permission.RECRUITING_APPLICATION_READ_ALL,
                ]
            )(self.list_jobs),
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
            RECRUITING_JOB_REQUEST_CLOSE_ENDPOINT,
            endpoint=authenticate(permissions=[Permission.RECRUITING_JOB_WRITE])(
                self.request_close
            ),
            methods=["POST"],
            response_model=None,
        )
        self.router.add_api_route(
            RECRUITING_JOB_REQUEST_REOPEN_ENDPOINT,
            endpoint=authenticate(permissions=[Permission.RECRUITING_JOB_WRITE])(
                self.request_reopen
            ),
            methods=["POST"],
            response_model=None,
        )
        self.router.add_api_route(
            RECRUITING_JOB_DISCARD_PENDING_EDIT_ENDPOINT,
            endpoint=authenticate(permissions=[Permission.RECRUITING_JOB_WRITE])(
                self.discard_pending_edit
            ),
            methods=["POST"],
            response_model=None,
        )
        self.router.add_api_route(
            RECRUITING_JOB_ENDPOINT,
            endpoint=authenticate(permissions=[Permission.RECRUITING_JOB_WRITE])(
                self.delete_job
            ),
            methods=["DELETE"],
            response_model=None,
        )
        self.router.add_api_route(
            RECRUITING_JOB_SUBMIT_ENDPOINT,
            endpoint=authenticate(permissions=[Permission.RECRUITING_JOB_WRITE])(
                self.submit_job
            ),
            methods=["POST"],
            response_model=None,
        )
        self.router.add_api_route(
            RECRUITING_APPROVERS_ENDPOINT,
            endpoint=authenticate(
                permissions=[
                    Permission.RECRUITING_JOB_READ,
                    Permission.RECRUITING_JOB_WRITE,
                    Permission.RECRUITING_JOB_APPROVE,
                ]
            )(self.list_approvers),
            methods=["GET"],
            response_model=None,
        )
        self.router.add_api_route(
            RECRUITING_INTERVIEW_POOL_ENDPOINT,
            endpoint=authenticate(
                permissions=[
                    Permission.RECRUITING_JOB_READ,
                    Permission.RECRUITING_JOB_WRITE,
                    Permission.RECRUITING_JOB_APPROVE,
                ]
            )(self.list_interview_pool),
            methods=["GET"],
            response_model=None,
        )
        self.router.add_api_route(
            RECRUITING_JOB_OWNERS_ENDPOINT,
            endpoint=authenticate(
                permissions=[
                    Permission.RECRUITING_JOB_READ,
                    Permission.RECRUITING_JOB_WRITE,
                    Permission.RECRUITING_JOB_APPROVE,
                ]
            )(self.list_job_owners),
            methods=["GET"],
            response_model=None,
        )
        self.router.add_api_route(
            RECRUITING_REVIEWS_ENDPOINT,
            endpoint=authenticate(permissions=[Permission.RECRUITING_JOB_APPROVE])(
                self.list_my_reviews
            ),
            methods=["GET"],
            response_model=None,
        )
        self.router.add_api_route(
            RECRUITING_REVIEW_ENDPOINT,
            endpoint=authenticate(permissions=[Permission.RECRUITING_JOB_APPROVE])(
                self.review_decision
            ),
            methods=["PATCH"],
            response_model=None,
        )
        self.router.add_api_route(
            RECRUITING_JOB_ENDPOINT,
            endpoint=authenticate(
                permissions=[
                    Permission.RECRUITING_JOB_READ,
                    Permission.RECRUITING_JOB_WRITE,
                    Permission.RECRUITING_JOB_APPROVE,
                    Permission.RECRUITING_APPLICATION_READ_ALL,
                ]
            )(self.get_job),
            methods=["GET"],
            response_model=None,
        )
        self.router.add_api_route(
            RECRUITING_JOB_ACTIVITY_ENDPOINT,
            endpoint=authenticate(
                permissions=[
                    Permission.RECRUITING_JOB_READ,
                    Permission.RECRUITING_JOB_WRITE,
                    Permission.RECRUITING_JOB_APPROVE,
                ]
            )(self.get_job_activity),
            methods=["GET"],
            response_model=None,
        )
        self.router.add_api_route(
            RECRUITING_EMAIL_SYNC_ENDPOINT,
            endpoint=authenticate(permissions=[Permission.SYSTEM_SYNC])(
                self.sync_recruiting_emails
            ),
            methods=["POST"],
            response_model=None,
        )
        self.router.add_api_route(
            RECRUITING_EMAIL_SYNC_RECENT_ENDPOINT,
            endpoint=authenticate(permissions=[Permission.SYSTEM_SYNC])(
                self.sync_recent_recruiting_emails
            ),
            methods=["POST"],
            response_model=None,
        )

    async def create_job(self, current_user: UserContextDto, job_data: JobCreateDto):
        """Create a DRAFT posting."""
        async with self.database.session() as session:
            result = await self.job_service.create_job(
                session, job_data, current_user.user_id
            )
        return api_response(message="Job created.", data=result)

    async def list_jobs(self, current_user: UserContextDto):
        """List postings of every status (internal view)."""
        async with self.database.session() as session:
            result = await self.job_service.list_all_jobs(session)
        return api_response(message="Jobs fetched.", data=result)

    async def update_job(
        self, current_user: UserContextDto, job_id: int, job_data: JobCreateDto
    ):
        """Update a posting (incl. form schema)."""
        async with self.database.session() as session:
            result = await self.job_service.update_job(session, job_id, job_data)
        return api_response(message="Job updated.", data=result)

    async def request_close(
        self,
        current_user: UserContextDto,
        job_id: int,
        submit_data: JobSubmitDto,
    ):
        """Request to close a PUBLISHED posting through the review gate."""
        async with self.database.session() as session:
            result = await self.job_service.request_close(
                session,
                job_id,
                submit_data.reviewer_id,
                current_user.user_id,
                submit_data.message,
            )
        return api_response(message="Close requested.", data=result)

    async def request_reopen(
        self,
        current_user: UserContextDto,
        job_id: int,
        submit_data: JobSubmitDto,
    ):
        """Request to reopen a CLOSED posting through the review gate."""
        async with self.database.session() as session:
            result = await self.job_service.request_reopen(
                session,
                job_id,
                submit_data.reviewer_id,
                current_user.user_id,
                submit_data.message,
            )
        return api_response(message="Reopen requested.", data=result)

    async def discard_pending_edit(self, current_user: UserContextDto, job_id: int):
        """Discard a posting's staged edit without changing its status."""
        async with self.database.session() as session:
            result = await self.job_service.discard_pending_edit(
                session, job_id, current_user.user_id
            )
        return api_response(message="Pending edit discarded.", data=result)

    async def delete_job(self, current_user: UserContextDto, job_id: int):
        """Delete a never-published CLOSED posting."""
        async with self.database.session() as session:
            await self.job_service.delete_job(session, job_id)
        return api_response(message="Job deleted.")

    async def submit_job(
        self,
        current_user: UserContextDto,
        job_id: int,
        submit_data: JobSubmitDto,
    ):
        """Submit a posting for review."""
        async with self.database.session() as session:
            result = await self.job_service.submit_for_review(
                session,
                job_id,
                submit_data.reviewer_id,
                current_user.user_id,
                submit_data.message,
            )
        return api_response(message="Job submitted for review.", data=result)

    async def list_approvers(self, current_user: UserContextDto):
        """List active users who may approve postings."""
        async with self.database.session() as session:
            result = await self.job_service.list_active_approvers(session)
        return api_response(message="Approvers fetched.", data=result)

    async def list_interview_pool(self, current_user: UserContextDto):
        """List users assignable as interview evaluators."""
        async with self.database.session() as session:
            result = await self.job_service.list_interview_pool(session)
        return api_response(message="Interview pool fetched.", data=result)

    async def list_job_owners(self, current_user: UserContextDto):
        """List users eligible to own a posting."""
        async with self.database.session() as session:
            result = await self.job_service.list_job_owners(session)
        return api_response(message="Job owners fetched.", data=result)

    async def list_my_reviews(self, current_user: UserContextDto):
        """List the current reviewer's pending reviews."""
        async with self.database.session() as session:
            result = await self.job_service.list_reviews_for_reviewer(
                session, current_user.user_id
            )
        return api_response(message="Reviews fetched.", data=result)

    async def review_decision(
        self,
        current_user: UserContextDto,
        review_id: int,
        decision_data: JobReviewDecisionDto,
    ):
        """Approve or reject a pending review."""
        async with self.database.session() as session:
            if decision_data.decision == "approve":
                result = await self.job_service.approve(
                    session, review_id, current_user.user_id
                )
                message = "Review approved."
            else:
                result = await self.job_service.reject(
                    session, review_id, decision_data.comment, current_user.user_id
                )
                message = "Review rejected."
        return api_response(message=message, data=result)

    async def get_job(self, current_user: UserContextDto, job_id: int):
        """Fetch one posting."""
        async with self.database.session() as session:
            result = await self.job_service.get_job(session, job_id)
        return api_response(message="Job fetched.", data=result)

    async def get_job_activity(self, current_user: UserContextDto, job_id: int):
        """Return a job posting's audit timeline, newest first."""
        async with self.database.session() as session:
            result = await self.job_service.get_job_activity(session, job_id)
        return api_response(message="Job activity fetched.", data=result)

    async def sync_recruiting_emails(self, current_user: UserContextDto):
        """Reconcile candidate email threads for every application in scope.

        Called by the weekly CronJob, not by a person: ``current_user`` is the
        service account and is deliberately unused — the sweep has no owner
        gate, which is why it lives here rather than in ``board_controller``.

        Succeeds with the counts even when individual applications failed. The
        CronJob runs ``curl -f`` under ``restartPolicy: OnFailure``, so a 5xx
        would make k8s re-run the entire sweep; one permanently-broken thread
        would then retry every night. Failures are reported in the body and,
        more importantly, in the log — see ``EmailSyncService``.
        """
        async with self.database.session() as session:
            summary = await self.email_sync_service.sync_due_applications(session)
        return api_response(message="Recruiting emails synced.", data=summary)

    async def sync_recent_recruiting_emails(self, current_user: UserContextDto):
        """Sync only the applications whose email threads just received mail.

        The nightly CronJob's entry point. One mailbox-wide Gmail lookup names
        the threads that changed, so this costs the same whether we track ten
        conversations or a thousand — unlike the full reconcile behind
        ``sync_recruiting_emails``, which the weekly CronJob calls.

        ``current_user`` is the service account and is deliberately unused.
        Succeeds with the counts even when individual applications failed, for
        the same reason as the reconcile endpoint — see ``EmailSyncService``.
        """
        async with self.database.session() as session:
            summary = await self.email_sync_service.sync_recent_applications(session)
        return api_response(message="Recent recruiting emails synced.", data=summary)
