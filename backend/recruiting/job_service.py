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

    async def list_interview_pool(self, session: AsyncSession) -> list[ApproverDto]:
        """List active users assignable as Screening/Behavioral/Tech evaluators.

        Args:
            session (AsyncSession): Active database async session.

        Returns:
            list[ApproverDto]: Holders of recruiting.interview.evaluate.
        """
        users = await self.user_permissions_repository.get_active_users_with_permission(
            session, Permission.RECRUITING_INTERVIEW_EVALUATE.value
        )
        return [self.recruiting_mapper.to_approver_dto(u) for u in users]

    async def list_job_owners(self, session: AsyncSession) -> list[ApproverDto]:
        """List active users eligible to own a posting (advance applications).

        Args:
            session (AsyncSession): Active database async session.

        Returns:
            list[ApproverDto]: Holders of recruiting.application.advance.
        """
        users = await self.user_permissions_repository.get_active_users_with_permission(
            session, Permission.RECRUITING_APPLICATION_ADVANCE.value
        )
        return [self.recruiting_mapper.to_approver_dto(u) for u in users]

    @staticmethod
    def _serialize(model) -> dict | None:
        """Dump a config sub-DTO to a camelCase JSONB dict, or None.

        Args:
            model: A BaseRequestDto config model (or None).

        Returns:
            dict | None: camelCase dict with unset optionals omitted, or None.
        """
        if model is None:
            return None
        return model.model_dump(mode="json", by_alias=True, exclude_none=True)

    @staticmethod
    def _pipeline_structure(cfg: dict | None) -> list:
        """Extract the re-reviewable structure of a pipeline (ignores owner/assignees).

        Args:
            cfg (dict | None): A serialized pipeline_config, or None.

        Returns:
            list: Ordered [(stage, rounds, referralSkippable)] tuples; [] if None.
        """
        if not cfg:
            return []
        return [
            (s.get("stage"), s.get("rounds"), s.get("referralSkippable", False))
            for s in cfg.get("stages", [])
        ]

    async def _validate_assignees_and_owner(
        self, session: AsyncSession, dto: JobCreateDto
    ) -> None:
        """Validate pre-configured assignees/owner hold the required permission.

        Each stage ``default_assignee_id`` must be an active holder of
        ``recruiting.interview.evaluate``; ``owner_id`` must be an active holder
        of ``recruiting.application.advance``. No-op when pipeline_config is unset.

        Args:
            session (AsyncSession): Active database async session.
            dto (JobCreateDto): The posting payload.

        Raises:
            ValueError: If any assignee/owner lacks the required permission.
        """
        if dto.pipeline_config is None:
            return
        assignee_ids = {
            s.default_assignee_id
            for s in dto.pipeline_config.stages
            if s.default_assignee_id is not None
        }
        if assignee_ids:
            pool = (
                await self.user_permissions_repository.get_active_users_with_permission(
                    session, Permission.RECRUITING_INTERVIEW_EVALUATE.value
                )
            )
            valid = {u.user_id for u in pool}
            missing = assignee_ids - valid
            if missing:
                raise ValueError(
                    f"default_assignee_id {sorted(missing)} are not active interview evaluators"
                )
        if dto.pipeline_config.owner_id is not None:
            pool = (
                await self.user_permissions_repository.get_active_users_with_permission(
                    session, Permission.RECRUITING_APPLICATION_ADVANCE.value
                )
            )
            if dto.pipeline_config.owner_id not in {u.user_id for u in pool}:
                raise ValueError(
                    f"owner_id {dto.pipeline_config.owner_id} cannot advance applications"
                )

    async def _revalidate_job_config(
        self, session: AsyncSession, job: "JobEntity"
    ) -> None:
        """Re-check the stored pipeline's assignees/owner before submission.

        Args:
            session (AsyncSession): Active database async session.
            job (JobEntity): The posting about to be submitted.

        Raises:
            ValueError: If a stored assignee/owner no longer holds its permission.
        """
        cfg = job.pipeline_config or {}
        assignee_ids = {
            s.get("defaultAssigneeId")
            for s in cfg.get("stages", [])
            if s.get("defaultAssigneeId") is not None
        }
        if assignee_ids:
            pool = (
                await self.user_permissions_repository.get_active_users_with_permission(
                    session, Permission.RECRUITING_INTERVIEW_EVALUATE.value
                )
            )
            missing = assignee_ids - {u.user_id for u in pool}
            if missing:
                raise ValueError(f"assignees {sorted(missing)} no longer qualify")
        owner_id = cfg.get("ownerId")
        if owner_id is not None:
            pool = (
                await self.user_permissions_repository.get_active_users_with_permission(
                    session, Permission.RECRUITING_APPLICATION_ADVANCE.value
                )
            )
            if owner_id not in {u.user_id for u in pool}:
                raise ValueError(f"owner {owner_id} no longer qualifies")

    async def create_job(self, session: AsyncSession, dto: JobCreateDto) -> JobDto:
        """Create a DRAFT posting from a JobCreateDto.

        Args:
            session (AsyncSession): Active database async session.
            dto (JobCreateDto): Payload with posting fields and config.

        Returns:
            JobDto: The newly created posting, including its assigned id.

        Raises:
            ValueError: If a pre-configured assignee/owner lacks its permission.
        """
        await self._validate_assignees_and_owner(session, dto)
        job = JobEntity(
            kind=dto.kind,
            mentorship_role=dto.mentorship_role,
            status=JobStatus.DRAFT,
            title=dto.title,
            description=dto.description,
            form_schema=self._serialize(dto.form_schema),
            pipeline_config=self._serialize(dto.pipeline_config),
            screen_rules=self._serialize(dto.screen_rules),
            profile_config=self._serialize(dto.profile_config),
        )
        job = await self.job_repository.create_job(session, job)
        await session.commit()
        return self.recruiting_mapper.to_job_dto(job)

    async def update_job(
        self, session: AsyncSession, job_id: int, dto: JobCreateDto
    ) -> JobDto:
        """Update a posting's editable fields.

        Only DRAFT and PUBLISHED postings are editable:
        - DRAFT: every field (title, description, kind, mentorship_role,
          form_schema, pipeline_config, screen_rules, profile_config) is
          written live directly.
        - PUBLISHED: changes are split into "contract" vs "operational".
          Contract changes (form_schema, profile_config, or the pipeline's
          structure = each stage's stage/rounds/referralSkippable) are parked
          in pending_form_schema/pending_pipeline_config/pending_profile_config
          and the status flips to PUBLISHED_PENDING_REVISION for re-review.
          Operational changes (title, description, screen_rules, and the
          pipeline's ownerId/defaultAssigneeId) are written live immediately.
          kind/mentorship_role are not editable once published.

        Any other status (PENDING_REVIEW, PUBLISHED_PENDING_REVISION,
        PENDING_CLOSE, PENDING_REOPEN, CLOSED) raises ValueError immediately
        without touching the entity.

        Args:
            session (AsyncSession): Active database async session.
            job_id (int): Identifier of the posting to update.
            dto (JobCreateDto): New values for editable fields.

        Returns:
            JobDto: The updated posting.

        Raises:
            ValueError: If no posting with the given id exists, the posting's
                current status is not DRAFT or PUBLISHED, or a pre-configured
                assignee/owner lacks its required permission.
        """
        job = await self._require_job(session, job_id)
        await self._validate_assignees_and_owner(session, dto)
        new_form = self._serialize(dto.form_schema)
        new_pipeline = self._serialize(dto.pipeline_config)
        new_screen = self._serialize(dto.screen_rules)
        new_profile = self._serialize(dto.profile_config)

        if job.status == JobStatus.DRAFT:
            job.title = dto.title
            job.description = dto.description
            job.kind = dto.kind
            job.mentorship_role = dto.mentorship_role
            job.form_schema = new_form
            job.pipeline_config = new_pipeline
            job.screen_rules = new_screen
            job.profile_config = new_profile
        elif job.status == JobStatus.PUBLISHED:
            # A None config field means "not provided / leave unchanged"
            # (JobCreateDto is a full-replacement body and the editor always
            # echoes the live config it is not editing). Only a provided field
            # whose contract differs triggers re-review.
            structural = (
                (new_form is not None and new_form != job.form_schema)
                or (new_profile is not None and new_profile != job.profile_config)
                or (
                    new_pipeline is not None
                    and self._pipeline_structure(new_pipeline)
                    != self._pipeline_structure(job.pipeline_config)
                )
            )
            # Operational levers apply live immediately.
            job.title = dto.title
            job.description = dto.description
            if new_screen is not None:
                job.screen_rules = new_screen
            if structural:
                job.pending_form_schema = new_form
                job.pending_pipeline_config = new_pipeline
                job.pending_profile_config = new_profile
                job.status = JobStatus.PUBLISHED_PENDING_REVISION
            elif new_pipeline is not None:
                # only owner/assignee (or title/desc/screen_rules) changed
                job.pipeline_config = new_pipeline
        else:
            raise ValueError(f"Job {job_id} cannot be edited from {job.status}")
        job = await self.job_repository.update_job(session, job)
        await session.commit()
        return self.recruiting_mapper.to_job_dto(job)

    async def _open_review(
        self,
        session: AsyncSession,
        job: "JobEntity",
        kind: JobReviewKind,
        reviewer_id: int,
        submitted_by: int,
        message: str | None,
        *,
        allowed_from: set,
        pending_status: JobStatus | None,
    ) -> JobDto:
        """Shared validation and creation logic for any review gate.

        Validates that the job's current status is in ``allowed_from``, that the
        job has no already-open review, that the submitter is not also the
        reviewer, that the active approver pool has at least ``MIN_APPROVER_POOL``
        members, and that the chosen reviewer is in that pool. Then creates a
        PENDING ``JobReviewEntity`` of ``kind``,
        optionally flips ``job.status`` to ``pending_status`` (when not None),
        persists, commits, and returns the updated JobDto.

        Args:
            session (AsyncSession): Active database async session.
            job (JobEntity): The posting being submitted for review.
            kind (JobReviewKind): The review gate type (INITIAL, REVISION, CLOSE,
                or REOPEN).
            reviewer_id (int): User who will review the posting; must hold the
                approve permission and differ from the submitter.
            submitted_by (int): User opening the review.
            message (str | None): Optional note to the reviewer.
            allowed_from (set): Set of JobStatus values the job must be in for
                the review to be valid.
            pending_status (JobStatus | None): Status to set on the job while
                the review is pending, or None to leave the status unchanged.

        Returns:
            JobDto: The posting after the review was opened.

        Raises:
            ValueError: If the job status is not in ``allowed_from``, the job
                already has an open review, the submitter picks themselves, the
                pool is too small, or the reviewer is not an active approver.
        """
        if job.status not in allowed_from:
            raise ValueError(
                f"Job {job.job_id} cannot open a {kind} review from {job.status}"
            )
        existing = await self.job_review_repository.get_open_for_job(
            session, job.job_id
        )
        if existing is not None:
            raise ValueError(f"Job {job.job_id} already has an open review")
        if reviewer_id == submitted_by:
            raise ValueError("Submitter cannot self-review the posting")

        approvers = await self.list_active_approvers(session)
        if len(approvers) < MIN_APPROVER_POOL:
            raise ValueError("Approver pool too small to submit for review")
        if reviewer_id not in {a.user_id for a in approvers}:
            raise ValueError("Reviewer is not an active approver")

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
        if pending_status is not None:
            job.status = pending_status
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
        await self._revalidate_job_config(session, job)
        if job.status == JobStatus.DRAFT:
            kind = JobReviewKind.INITIAL
            pending_status: JobStatus | None = JobStatus.PENDING_REVIEW
        elif job.status == JobStatus.PUBLISHED_PENDING_REVISION:
            kind = JobReviewKind.REVISION
            pending_status = None  # live version stays public; status unchanged
        else:
            raise ValueError(f"Job {job_id} cannot be submitted from {job.status}")
        return await self._open_review(
            session,
            job,
            kind,
            reviewer_id,
            submitted_by,
            message,
            allowed_from={job.status},
            pending_status=pending_status,
        )

    async def request_close(
        self,
        session: AsyncSession,
        job_id: int,
        reviewer_id: int,
        submitted_by: int,
        message: str | None,
    ) -> JobDto:
        """Open a close-review for a PUBLISHED posting.

        The posting moves to PENDING_CLOSE while the review is pending. Only a
        PUBLISHED posting may be closed via review; drafts may be closed
        directly via ``close_job``.

        Args:
            session (AsyncSession): Active database async session.
            job_id (int): Posting to close.
            reviewer_id (int): Chosen approver; must hold the approve permission
                and differ from the submitter.
            submitted_by (int): User requesting the close.
            message (str | None): Optional note to the reviewer.

        Returns:
            JobDto: The posting with status PENDING_CLOSE.

        Raises:
            ValueError: If the posting is not PUBLISHED, the submitter picks
                themselves, the pool is too small, or the reviewer is not an
                active approver.
        """
        job = await self._require_job(session, job_id)
        return await self._open_review(
            session,
            job,
            JobReviewKind.CLOSE,
            reviewer_id,
            submitted_by,
            message,
            allowed_from={JobStatus.PUBLISHED},
            pending_status=JobStatus.PENDING_CLOSE,
        )

    async def request_reopen(
        self,
        session: AsyncSession,
        job_id: int,
        reviewer_id: int,
        submitted_by: int,
        message: str | None,
    ) -> JobDto:
        """Open a reopen-review for a CLOSED posting.

        The posting moves to PENDING_REOPEN while the review is pending. On
        approval it becomes PUBLISHED; on rejection it stays CLOSED.

        Args:
            session (AsyncSession): Active database async session.
            job_id (int): Posting to reopen.
            reviewer_id (int): Chosen approver; must hold the approve permission
                and differ from the submitter.
            submitted_by (int): User requesting the reopen.
            message (str | None): Optional note to the reviewer.

        Returns:
            JobDto: The posting with status PENDING_REOPEN.

        Raises:
            ValueError: If the posting is not CLOSED, the submitter picks
                themselves, the pool is too small, or the reviewer is not an
                active approver.
        """
        job = await self._require_job(session, job_id)
        return await self._open_review(
            session,
            job,
            JobReviewKind.REOPEN,
            reviewer_id,
            submitted_by,
            message,
            allowed_from={JobStatus.CLOSED},
            pending_status=JobStatus.PENDING_REOPEN,
        )

    async def approve(
        self, session: AsyncSession, review_id: int, acting_user_id: int
    ) -> JobDto:
        """Approve a pending review, advancing the posting to its next state.

        Review-kind state machine on approval:
        - INITIAL: posting moves to PUBLISHED.
        - REVISION: pending_* values are swapped into live fields, cleared, and
          the posting moves to PUBLISHED.
        - CLOSE: posting moves to CLOSED.
        - REOPEN: posting moves to PUBLISHED.

        Args:
            session (AsyncSession): Active database async session.
            review_id (int): The review to approve.
            acting_user_id (int): The authenticated user making the decision;
                must be the review's assigned reviewer.

        Returns:
            JobDto: The posting after approval.

        Raises:
            ValueError: If the review is missing, not pending, or the acting
                user is not the assigned reviewer.
        """
        review = await self._require_pending_review(session, review_id, acting_user_id)
        review.status = JobReviewStatus.APPROVED
        review.decided_at = datetime.now(timezone.utc)

        job = await self._require_job(session, review.job_id)
        if review.kind == JobReviewKind.CLOSE:
            job.status = JobStatus.CLOSED
        elif review.kind == JobReviewKind.REOPEN:
            job.status = JobStatus.PUBLISHED
            job.was_published = True
        else:
            # INITIAL or REVISION
            if job.status == JobStatus.PUBLISHED_PENDING_REVISION:
                if review.kind == JobReviewKind.REVISION:
                    job.form_schema = job.pending_form_schema or job.form_schema
                    job.pipeline_config = (
                        job.pending_pipeline_config or job.pipeline_config
                    )
                    job.profile_config = (
                        job.pending_profile_config or job.profile_config
                    )
                job.pending_form_schema = None
                job.pending_pipeline_config = None
                job.pending_profile_config = None
            job.status = JobStatus.PUBLISHED
            job.was_published = True
        job = await self.job_repository.update_job(session, job)
        await session.commit()
        return self.recruiting_mapper.to_job_dto(job)

    async def reject(
        self, session: AsyncSession, review_id: int, comment: str, acting_user_id: int
    ) -> JobDto:
        """Reject a pending review.

        Review-kind state machine on rejection:
        - INITIAL: posting returns to DRAFT.
        - REVISION: pending_* values are discarded and the posting stays PUBLISHED.
        - CLOSE: the close is aborted and the posting returns to PUBLISHED.
        - REOPEN: the reopen is aborted and the posting remains CLOSED.

        Args:
            session (AsyncSession): Active database async session.
            review_id (int): The review to reject.
            comment (str): Required reviewer feedback.
            acting_user_id (int): The authenticated user making the decision;
                must be the review's assigned reviewer.

        Returns:
            JobDto: The posting after rejection.

        Raises:
            ValueError: If the comment is empty, the review is missing/decided,
                or the acting user is not the assigned reviewer.
        """
        if not comment or not comment.strip():
            raise ValueError("A comment is required to reject a posting")
        review = await self._require_pending_review(session, review_id, acting_user_id)
        review.status = JobReviewStatus.REJECTED
        review.reject_comment = comment
        review.decided_at = datetime.now(timezone.utc)

        job = await self._require_job(session, review.job_id)
        if review.kind == JobReviewKind.REVISION:
            job.pending_form_schema = None
            job.pending_pipeline_config = None
            job.pending_profile_config = None
            job.status = JobStatus.PUBLISHED
        elif review.kind == JobReviewKind.CLOSE:
            # Abort the close — posting goes back to PUBLISHED.
            job.status = JobStatus.PUBLISHED
        elif review.kind == JobReviewKind.REOPEN:
            # Abort the reopen — posting stays CLOSED.
            job.status = JobStatus.CLOSED
        else:
            # INITIAL rejection sends the posting back to DRAFT.
            job.status = JobStatus.DRAFT
        job = await self.job_repository.update_job(session, job)
        await session.commit()
        return self.recruiting_mapper.to_job_dto(job)

    async def _require_pending_review(
        self, session: AsyncSession, review_id: int, acting_user_id: int
    ) -> JobReviewEntity:
        """Return the pending review for review_id, or raise ValueError.

        Args:
            session (AsyncSession): Active database async session.
            review_id (int): Identifier to look up.
            acting_user_id (int): The authenticated user making the decision;
                must be the review's assigned reviewer.

        Returns:
            JobReviewEntity: The pending review.

        Raises:
            ValueError: If the review is missing, already decided, or the acting
                user is not the assigned reviewer.
        """
        # Lock the row so two concurrent decisions on the same review serialise:
        # the second blocks until the first commits, then sees a non-pending
        # status below and is rejected.
        review = await self.job_review_repository.get(
            session, review_id, for_update=True
        )
        if review is None:
            raise ValueError(f"Review {review_id} not found")
        if review.status != JobReviewStatus.PENDING:
            raise ValueError(f"Review {review_id} is not pending")
        if review.reviewer_id != acting_user_id:
            # Only the assigned reviewer may decide. Because submit_for_review
            # rejects reviewer == submitter, enforcing this here also prevents a
            # submitter from approving or rejecting their own posting.
            raise ValueError(
                f"Only the assigned reviewer may decide review {review_id}"
            )
        return review

    async def close_job(self, session: AsyncSession, job_id: int) -> JobDto:
        """Directly close a DRAFT posting without a review cycle.

        Only DRAFT postings may be closed directly. Published postings must go
        through the review gate via ``request_close``; this restriction prevents
        accidentally bypassing approver oversight for live postings.

        Args:
            session (AsyncSession): Active database async session.
            job_id (int): Identifier of the posting to close.

        Returns:
            JobDto: The posting with status CLOSED.

        Raises:
            ValueError: If the posting does not exist or is not a DRAFT (use
                ``request_close`` instead).
        """
        job = await self._require_job(session, job_id)
        if job.status != JobStatus.DRAFT:
            raise ValueError(
                f"Job {job_id} is not a draft; use request_close to close a published posting"
            )
        job.status = JobStatus.CLOSED
        job = await self.job_repository.update_job(session, job)
        await session.commit()
        return self.recruiting_mapper.to_job_dto(job)

    async def delete_job(self, session: AsyncSession, job_id: int) -> None:
        """Delete a posting that was never published.

        Only a CLOSED posting that was never published (``was_published`` is
        ``False``) may be deleted. Once a posting has ever been published it
        cannot be deleted regardless of its current status.

        Args:
            session (AsyncSession): Active database async session.
            job_id (int): Identifier of the posting to delete.

        Raises:
            ValueError: If the posting does not exist, is not CLOSED, or has
                ever been published.
        """
        job = await self._require_job(session, job_id)
        if job.status != JobStatus.CLOSED or job.was_published:
            raise ValueError(
                f"Job {job_id} cannot be deleted: only never-published CLOSED postings may be deleted"
            )
        await self.job_repository.delete_job(session, job)
        await session.commit()

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
