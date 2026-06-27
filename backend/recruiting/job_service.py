from datetime import datetime, timezone

from backend.entity.job_entity import JobEntity
from backend.entity.job_review_entity import JobReviewEntity
from backend.repository.job_repository import JobRepository
from backend.repository.job_review_repository import JobReviewRepository
from backend.repository.user_permissions_repository import UserPermissionsRepository
from backend.recruiting.recruiting_mapper import RecruitingMapper
from backend.dto.job_dto import JobCreateDto, JobDto
from backend.dto.job_review_dto import ApproverDto, JobReviewDto
from backend.common.permissions import Permission
from backend.common.recruiting_enums import (
    JobReviewKind,
    JobReviewStatus,
    JobStatus,
)
from sqlalchemy.ext.asyncio import AsyncSession

MIN_APPROVER_POOL = 2


class JobService:
    """Manages recruiting postings (create/edit/close + review gate)."""

    def __init__(
        self,
        job_repository: JobRepository,
        recruiting_mapper: RecruitingMapper,
        user_permissions_repository: UserPermissionsRepository,
        job_review_repository: JobReviewRepository,
    ):
        """
        Initialise the service with its repositories and mapper.

        Args:
            job_repository (JobRepository): Data-access layer for JobEntity.
            recruiting_mapper (RecruitingMapper): Entity-to-DTO converter.
            user_permissions_repository (UserPermissionsRepository): Used to
                resolve who may approve postings.
            job_review_repository (JobReviewRepository): Data-access layer for
                JobReviewEntity (the review gate).
        """
        self.job_repository = job_repository
        self.recruiting_mapper = recruiting_mapper
        self.user_permissions_repository = user_permissions_repository
        self.job_review_repository = job_review_repository

    async def list_active_approvers(self, session: AsyncSession) -> list[ApproverDto]:
        """List active users who may approve postings (hold job.approve).

        Args:
            session (AsyncSession): Active database async session.

        Returns:
            list[ApproverDto]: One entry per active approver.
        """
        users = await self.user_permissions_repository.get_active_users_with_permission(
            session, Permission.RECRUITING_JOB_APPROVE.value
        )
        return [self.recruiting_mapper.to_approver_dto(u) for u in users]

    async def create_job(self, session: AsyncSession, dto: JobCreateDto) -> JobDto:
        """Create a DRAFT posting from a JobCreateDto.

        Args:
            session (AsyncSession): Active database async session.
            dto (JobCreateDto): Payload with posting fields.

        Returns:
            JobDto: The newly created posting, including its assigned id.
        """
        job = JobEntity(
            kind=dto.kind,
            mentorship_role=dto.mentorship_role,
            status=JobStatus.DRAFT,
            title=dto.title,
            description=dto.description,
            form_schema=dto.form_schema,
            pipeline_config=dto.pipeline_config,
        )
        job = await self.job_repository.create_job(session, job)
        await session.commit()
        return self.recruiting_mapper.to_job_dto(job)

    async def update_job(
        self, session: AsyncSession, job_id: int, dto: JobCreateDto
    ) -> JobDto:
        """Update a posting's editable fields.

        A DRAFT posting is edited in place. Editing the form schema or pipeline
        of a PUBLISHED posting does not touch the live version: the change is
        parked in pending_form_schema/pending_pipeline_config and the status
        flips to PUBLISHED_PENDING_REVISION until a reviewer approves it.

        Args:
            session (AsyncSession): Active database async session.
            job_id (int): Identifier of the posting to update.
            dto (JobCreateDto): New values for editable fields.

        Returns:
            JobDto: The updated posting.

        Raises:
            ValueError: If no posting with the given id exists.
        """
        job = await self._require_job(session, job_id)
        if job.status == JobStatus.PUBLISHED and (
            dto.form_schema != job.form_schema
            or dto.pipeline_config != job.pipeline_config
        ):
            job.pending_form_schema = dto.form_schema
            job.pending_pipeline_config = dto.pipeline_config
            job.status = JobStatus.PUBLISHED_PENDING_REVISION
        else:
            job.title = dto.title
            job.description = dto.description
            job.kind = dto.kind
            job.mentorship_role = dto.mentorship_role
            job.form_schema = dto.form_schema
            job.pipeline_config = dto.pipeline_config
        job = await self.job_repository.update_job(session, job)
        await session.commit()
        return self.recruiting_mapper.to_job_dto(job)

    async def submit_for_review(
        self,
        session: AsyncSession,
        job_id: int,
        reviewer_id: int,
        submitted_by: int,
        message: str | None,
    ) -> JobDto:
        """Submit a posting for review, opening a pending review cycle.

        A DRAFT submission is an INITIAL review and moves the posting to
        PENDING_REVIEW. Submitting a PUBLISHED_PENDING_REVISION is a REVISION
        review and leaves the status unchanged (the live version stays public).

        Args:
            session (AsyncSession): Active database async session.
            job_id (int): Posting being submitted.
            reviewer_id (int): Chosen approver; must hold the approve permission
                and differ from the submitter.
            submitted_by (int): User submitting the posting.
            message (str | None): Optional note to the reviewer.

        Returns:
            JobDto: The posting after submission.

        Raises:
            ValueError: If the posting cannot be submitted from its current
                status, the submitter picks themselves, the approver pool is
                too small, or the reviewer is not an active approver.
        """
        job = await self._require_job(session, job_id)
        if job.status not in (
            JobStatus.DRAFT,
            JobStatus.PUBLISHED_PENDING_REVISION,
        ):
            raise ValueError(f"Job {job_id} cannot be submitted from {job.status}")
        if reviewer_id == submitted_by:
            raise ValueError("Submitter cannot self-review the posting")

        approvers = await self.list_active_approvers(session)
        if len(approvers) < MIN_APPROVER_POOL:
            raise ValueError("Approver pool too small to submit for review")
        if reviewer_id not in {a.user_id for a in approvers}:
            raise ValueError("Reviewer is not an active approver")

        kind = (
            JobReviewKind.INITIAL
            if job.status == JobStatus.DRAFT
            else JobReviewKind.REVISION
        )
        await self.job_review_repository.create(
            session,
            JobReviewEntity(
                job_id=job.job_id,
                submitted_by=submitted_by,
                reviewer_id=reviewer_id,
                status=JobReviewStatus.PENDING,
                kind=kind,
                submit_message=message,
            ),
        )
        if job.status == JobStatus.DRAFT:
            job.status = JobStatus.PENDING_REVIEW
            job = await self.job_repository.update_job(session, job)
        await session.commit()
        return self.recruiting_mapper.to_job_dto(job)

    async def approve(self, session: AsyncSession, review_id: int) -> JobDto:
        """Approve a pending review, publishing the posting.

        For a REVISION the parked pending_* values are swapped into the live
        fields and cleared; the posting becomes PUBLISHED either way.

        Args:
            session (AsyncSession): Active database async session.
            review_id (int): The review to approve.

        Returns:
            JobDto: The published posting.

        Raises:
            ValueError: If the review is missing or not pending.
        """
        review = await self._require_pending_review(session, review_id)
        review.status = JobReviewStatus.APPROVED
        review.decided_at = datetime.now(timezone.utc)

        job = await self._require_job(session, review.job_id)
        if job.status == JobStatus.PUBLISHED_PENDING_REVISION:
            if review.kind == JobReviewKind.REVISION:
                job.form_schema = job.pending_form_schema or job.form_schema
                job.pipeline_config = job.pending_pipeline_config or job.pipeline_config
            job.pending_form_schema = None
            job.pending_pipeline_config = None
        job.status = JobStatus.PUBLISHED
        job = await self.job_repository.update_job(session, job)
        await session.commit()
        return self.recruiting_mapper.to_job_dto(job)

    async def reject(
        self, session: AsyncSession, review_id: int, comment: str
    ) -> JobDto:
        """Reject a pending review.

        An INITIAL rejection returns the posting to DRAFT. A REVISION rejection
        discards the parked change and leaves the live posting PUBLISHED.

        Args:
            session (AsyncSession): Active database async session.
            review_id (int): The review to reject.
            comment (str): Required reviewer feedback.

        Returns:
            JobDto: The posting after rejection.

        Raises:
            ValueError: If the comment is empty or the review is missing/decided.
        """
        if not comment or not comment.strip():
            raise ValueError("A comment is required to reject a posting")
        review = await self._require_pending_review(session, review_id)
        review.status = JobReviewStatus.REJECTED
        review.reject_comment = comment
        review.decided_at = datetime.now(timezone.utc)

        job = await self._require_job(session, review.job_id)
        if review.kind == JobReviewKind.REVISION:
            job.pending_form_schema = None
            job.pending_pipeline_config = None
            job.status = JobStatus.PUBLISHED
        else:
            job.status = JobStatus.DRAFT
        job = await self.job_repository.update_job(session, job)
        await session.commit()
        return self.recruiting_mapper.to_job_dto(job)

    async def _require_pending_review(
        self, session: AsyncSession, review_id: int
    ) -> JobReviewEntity:
        """Return the pending review for review_id, or raise ValueError.

        Args:
            session (AsyncSession): Active database async session.
            review_id (int): Identifier to look up.

        Returns:
            JobReviewEntity: The pending review.

        Raises:
            ValueError: If the review is missing or already decided.
        """
        review = await self.job_review_repository.get(session, review_id)
        if review is None:
            raise ValueError(f"Review {review_id} not found")
        if review.status != JobReviewStatus.PENDING:
            raise ValueError(f"Review {review_id} is not pending")
        return review

    async def close_job(self, session: AsyncSession, job_id: int) -> JobDto:
        """Transition a posting to CLOSED.

        Args:
            session (AsyncSession): Active database async session.
            job_id (int): Identifier of the posting to close.

        Returns:
            JobDto: The posting with status CLOSED.

        Raises:
            ValueError: If no posting with the given id exists.
        """
        job = await self._require_job(session, job_id)
        job.status = JobStatus.CLOSED
        job = await self.job_repository.update_job(session, job)
        await session.commit()
        return self.recruiting_mapper.to_job_dto(job)

    async def reopen_job(self, session: AsyncSession, job_id: int) -> JobDto:
        """Reopen a CLOSED posting, returning it to PUBLISHED.

        Args:
            session (AsyncSession): Active database async session.
            job_id (int): Identifier of the posting to reopen.

        Returns:
            JobDto: The posting with status PUBLISHED.

        Raises:
            ValueError: If the posting does not exist or is not CLOSED.
        """
        job = await self._require_job(session, job_id)
        if job.status != JobStatus.CLOSED:
            raise ValueError(f"Job {job_id} is not closed; cannot reopen")
        job.status = JobStatus.PUBLISHED
        job = await self.job_repository.update_job(session, job)
        await session.commit()
        return self.recruiting_mapper.to_job_dto(job)

    async def list_published(self, session: AsyncSession) -> list[JobDto]:
        """List all PUBLISHED postings.

        Args:
            session (AsyncSession): Active database async session.

        Returns:
            list[JobDto]: All currently published postings.
        """
        jobs = await self.job_repository.list_published(session)
        return [self.recruiting_mapper.to_job_dto(j) for j in jobs]

    async def list_all_jobs(self, session: AsyncSession) -> list[JobDto]:
        """List postings of every status (internal/admin view).

        Each posting is annotated with the reject_comment from its most-recent
        review when that review was a rejection, so the creator can see the
        posting was sent back and why. The field self-clears once a newer
        (non-rejected) review becomes the latest.

        Args:
            session (AsyncSession): Active database async session.

        Returns:
            list[JobDto]: All postings regardless of status, each carrying
            ``last_reject_comment`` if the posting's latest review was a
            rejection, otherwise ``None``.
        """
        jobs = await self.job_repository.list_all(session)
        latest_reviews = await self.job_review_repository.get_latest_reviews(
            session, [j.job_id for j in jobs]
        )
        dtos = []
        for j in jobs:
            latest = latest_reviews.get(j.job_id)
            comment = (
                latest.reject_comment
                if latest is not None and latest.status == JobReviewStatus.REJECTED
                else None
            )
            dtos.append(
                self.recruiting_mapper.to_job_dto(j, last_reject_comment=comment)
            )
        return dtos

    async def list_reviews_for_reviewer(
        self, session: AsyncSession, reviewer_id: int
    ) -> list[JobReviewDto]:
        """List a reviewer's still-pending review requests, each with its job title.

        Args:
            session (AsyncSession): Active database async session.
            reviewer_id (int): The reviewer whose queue to fetch.

        Returns:
            list[JobReviewDto]: The reviewer's pending reviews. Each entry
            includes ``job_title`` sourced from the associated posting so the
            UI can display the title without a second request.
        """
        reviews = await self.job_review_repository.list_by_reviewer(
            session, reviewer_id, [JobReviewStatus.PENDING]
        )
        dtos = []
        for r in reviews:
            job = await self.job_repository.get_by_job_id(session, r.job_id)
            dtos.append(
                self.recruiting_mapper.to_job_review_dto(
                    r, job_title=job.title if job else None
                )
            )
        return dtos

    async def get_job(self, session: AsyncSession, job_id: int) -> JobDto:
        """Fetch one posting by id.

        Args:
            session (AsyncSession): Active database async session.
            job_id (int): Identifier of the posting to retrieve.

        Returns:
            JobDto: The requested posting.

        Raises:
            ValueError: If no posting with the given id exists.
        """
        job = await self._require_job(session, job_id)
        return self.recruiting_mapper.to_job_dto(job)

    async def _require_job(self, session: AsyncSession, job_id: int) -> JobEntity:
        """Return the JobEntity for job_id, or raise ValueError if absent.

        Args:
            session (AsyncSession): Active database async session.
            job_id (int): Identifier to look up.

        Returns:
            JobEntity: The found entity.

        Raises:
            ValueError: If the job does not exist.
        """
        job = await self.job_repository.get_by_job_id(session, job_id)
        if job is None:
            raise ValueError(f"Job {job_id} not found")
        return job
