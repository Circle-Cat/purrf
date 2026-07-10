from datetime import datetime, timezone

from backend.entity.job_entity import JobEntity
from backend.entity.job_review_entity import JobReviewEntity
from backend.entity.notification_entity import NotificationEntity
from backend.repository.job_activity_repository import JobActivityRepository
from backend.repository.job_repository import JobRepository
from backend.repository.job_review_repository import JobReviewRepository
from backend.repository.user_permissions_repository import UserPermissionsRepository
from backend.repository.users_repository import UsersRepository
from backend.recruiting.pipeline_owners import normalized_owner_ids
from backend.recruiting.recruiting_mapper import RecruitingMapper
from backend.dto.job_dto import JobCreateDto, JobDto, PublicJobDto, PublicJobSummaryDto
from backend.dto.job_review_dto import ApproverDto, JobReviewDto
from backend.common.permissions import Permission
from backend.common.recruiting_enums import (
    JobReviewKind,
    JobReviewStatus,
    JobStatus,
    NotificationType,
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
        notification_repository,
        users_repository: UsersRepository,
        job_activity_repository: JobActivityRepository,
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
            notification_repository (NotificationRepository): Written by
                ``_open_review`` (reviewer notified) and ``approve``/
                ``reject`` (submitter notified of the decision).
            users_repository (UsersRepository): Actor-name resolution for the
                audit timeline.
            job_activity_repository (JobActivityRepository): Data-access layer
                for the append-only audit timeline.
        """
        self.job_repository = job_repository
        self.recruiting_mapper = recruiting_mapper
        self.user_permissions_repository = user_permissions_repository
        self.job_review_repository = job_review_repository
        self.notification_repository = notification_repository
        self.users_repository = users_repository
        self.job_activity_repository = job_activity_repository

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
    def _build_pending_payload(job: "JobEntity", dto: JobCreateDto) -> dict:
        """Merge an edit dto onto a posting's current live values.

        Optional config fields (screen_rules, form_schema, pipeline_config,
        profile_config) fall back to the posting's current live value when the
        dto sends None, so a field the submitter didn't touch is never blanked
        out when this payload is later applied. title and cooldown_days are
        carried through as-is: title is required non-null on the dto, and
        cooldown_days's None is an explicit clear (existing behavior), not
        "leave unchanged".

        Args:
            job (JobEntity): The posting being edited.
            dto (JobCreateDto): The incoming edit payload.

        Returns:
            dict: A complete camelCase draft snapshot of all seven editable
            fields, ready to store as pending_payload and later apply verbatim.
        """
        new_form = JobService._serialize(dto.form_schema)
        new_pipeline = JobService._serialize(dto.pipeline_config)
        new_screen = JobService._serialize(dto.screen_rules)
        new_profile = JobService._serialize(dto.profile_config)
        return {
            "title": dto.title,
            "description": dto.description,
            "cooldownDays": dto.cooldown_days,
            "screenRules": new_screen if new_screen is not None else job.screen_rules,
            "formSchema": new_form if new_form is not None else job.form_schema,
            "pipelineConfig": (
                new_pipeline if new_pipeline is not None else job.pipeline_config
            ),
            "profileConfig": (
                new_profile if new_profile is not None else job.profile_config
            ),
        }

    @staticmethod
    def _apply_pending_payload(job: "JobEntity") -> None:
        """Overwrite a posting's live fields with its pending_payload, then clear it.

        Reads each field via ``dict.get`` rather than indexing, so a payload
        missing a key degrades to clearing that field to None instead of
        raising KeyError.

        Args:
            job (JobEntity): The posting; job.pending_payload must not be None.
        """
        payload = job.pending_payload
        job.title = payload.get("title")
        job.description = payload.get("description")
        job.cooldown_days = payload.get("cooldownDays")
        job.screen_rules = payload.get("screenRules")
        job.form_schema = payload.get("formSchema")
        job.pipeline_config = payload.get("pipelineConfig")
        job.profile_config = payload.get("profileConfig")
        job.pending_payload = None

    async def _validate_assignees_and_owner(
        self, session: AsyncSession, dto: JobCreateDto
    ) -> None:
        """Validate pre-configured assignees/owners hold the required permission.

        Each stage ``default_assignee_id`` must be an active holder of
        ``recruiting.interview.evaluate``; every id in ``owner_ids`` must be an
        active holder of ``recruiting.application.advance``. No-op when
        pipeline_config is unset.

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
        owner_ids = dto.pipeline_config.owner_ids
        if owner_ids:
            pool = (
                await self.user_permissions_repository.get_active_users_with_permission(
                    session, Permission.RECRUITING_APPLICATION_ADVANCE.value
                )
            )
            valid = {u.user_id for u in pool}
            missing = [o for o in owner_ids if o not in valid]
            if missing:
                raise ValueError(
                    f"owner_ids {sorted(missing)} cannot advance applications"
                )

    async def _revalidate_job_config(
        self, session: AsyncSession, job: "JobEntity"
    ) -> None:
        """Re-check the stored pipeline's assignees/owners before submission.

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
        owner_ids = normalized_owner_ids(cfg)
        if owner_ids:
            pool = (
                await self.user_permissions_repository.get_active_users_with_permission(
                    session, Permission.RECRUITING_APPLICATION_ADVANCE.value
                )
            )
            valid = {u.user_id for u in pool}
            missing_owners = [o for o in owner_ids if o not in valid]
            if missing_owners:
                raise ValueError(f"owners {sorted(missing_owners)} no longer qualify")

    async def create_job(
        self, session: AsyncSession, dto: JobCreateDto, created_by: int
    ) -> JobDto:
        """Create a DRAFT posting from a JobCreateDto.

        Args:
            session (AsyncSession): Active database async session.
            dto (JobCreateDto): Payload with posting fields and config.
            created_by (int): The authenticated user creating the posting,
                logged as the ``job_created`` audit entry's actor.

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
            cooldown_days=dto.cooldown_days,
        )
        job = await self.job_repository.create_job(session, job)
        await self.job_activity_repository.create(
            session, job.job_id, created_by, "job_created"
        )
        await session.commit()
        return self.recruiting_mapper.to_job_dto(job)

    async def update_job(
        self, session: AsyncSession, job_id: int, dto: JobCreateDto
    ) -> JobDto:
        """Update a posting's editable fields.

        Only DRAFT, PUBLISHED, and CLOSED postings are editable:
        - DRAFT: every field (title, description, kind, mentorship_role,
          form_schema, pipeline_config, screen_rules, profile_config,
          cooldown_days) is written live directly.
        - PUBLISHED: any edit — every field, no exceptions — is packed into
          pending_payload and the status flips to PUBLISHED_PENDING_REVISION
          for re-review. The live version stays public and unchanged until
          the revision is approved. kind/mentorship_role are not editable
          once published — the UI disables both fields, and a differing
          value here raises rather than being silently dropped.
        - CLOSED: same rule as PUBLISHED — any edit parks into pending_payload;
          status is unchanged (still CLOSED). Use request_reopen separately to
          submit the posting (with or without this edit) for a REOPEN review.
          A CLOSED posting that was never published cannot be edited — there
          is no review path that would ever apply a staged edit on it, so it
          is rejected outright (delete_job instead).

        Any other status (PENDING_REVIEW, PUBLISHED_PENDING_REVISION,
        PENDING_CLOSE, PENDING_REOPEN) raises ValueError immediately
        without touching the entity.

        Args:
            session (AsyncSession): Active database async session.
            job_id (int): Identifier of the posting to update.
            dto (JobCreateDto): New values for editable fields.

        Returns:
            JobDto: The updated posting.

        Raises:
            ValueError: If no posting with the given id exists, the posting's
                current status is not DRAFT, PUBLISHED, or CLOSED (i.e. it is
                PENDING_REVIEW, PUBLISHED_PENDING_REVISION, PENDING_CLOSE, or
                PENDING_REOPEN), the posting is CLOSED but was never
                published, a PUBLISHED/CLOSED edit tries to change kind or
                mentorship_role, or a pre-configured assignee/owner lacks its
                required permission.
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
            job.cooldown_days = dto.cooldown_days
        elif job.status == JobStatus.PUBLISHED:
            self._require_unchanged_kind(job_id, job, dto)
            job.pending_payload = self._build_pending_payload(job, dto)
            job.status = JobStatus.PUBLISHED_PENDING_REVISION
        elif job.status == JobStatus.CLOSED:
            if not job.was_published:
                raise ValueError(
                    f"Job {job_id} was never published; delete it instead of editing"
                )
            self._require_unchanged_kind(job_id, job, dto)
            job.pending_payload = self._build_pending_payload(job, dto)
        else:
            raise ValueError(f"Job {job_id} cannot be edited from {job.status}")
        job = await self.job_repository.update_job(session, job)
        await session.commit()
        return self.recruiting_mapper.to_job_dto(job)

    @staticmethod
    def _require_unchanged_kind(
        job_id: int, job: "JobEntity", dto: JobCreateDto
    ) -> None:
        """Reject an edit that changes kind or mentorship_role once a posting
        has left DRAFT — both fields are locked from that point on. The UI
        disables them; this is the backend's defense in depth for a caller
        that bypasses it.

        Args:
            job_id (int): The posting being edited, for the error message.
            job (JobEntity): The posting's current, live values.
            dto (JobCreateDto): The incoming edit payload.

        Raises:
            ValueError: If dto.kind or dto.mentorship_role differs from the
                posting's current value.
        """
        if dto.kind != job.kind or dto.mentorship_role != job.mentorship_role:
            raise ValueError(
                f"Job {job_id} cannot change kind or mentorship role once it "
                "has left draft"
            )

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

        review = await self.job_review_repository.create(
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
        await self.job_activity_repository.create(
            session,
            job.job_id,
            submitted_by,
            "review_opened",
            {"kind": kind.value, "reviewerId": reviewer_id, "message": message},
        )
        if reviewer_id != submitted_by:
            await self.notification_repository.create(
                session,
                NotificationEntity(
                    user_id=reviewer_id,
                    type=NotificationType.JOB_REVIEW_REQUESTED,
                    job_id=job.job_id,
                    job_review_id=review.review_id,
                    actor_user_id=submitted_by,
                ),
            )
        if pending_status is not None:
            job.status = pending_status
            job = await self.job_repository.update_job(session, job)
        await session.commit()
        return self.recruiting_mapper.to_job_dto(job, reviewer_id=reviewer_id)

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
            ValueError: If the posting is not CLOSED, was never published
                (use delete_job instead), the submitter picks themselves,
                the pool is too small, or the reviewer is not an active
                approver.
        """
        job = await self._require_job(session, job_id)
        if not job.was_published:
            raise ValueError(
                f"Job {job_id} was never published; delete it instead of reopening"
            )
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
        - REVISION: pending_payload is applied to live fields and cleared, and
          the posting moves to PUBLISHED.
        - CLOSE: posting moves to CLOSED.
        - REOPEN: if a pending_payload exists it is applied to live fields
          and cleared, then the posting moves to PUBLISHED.

        Also inserts a JOB_REVIEW_APPROVED notification for the review's
        submitter, unless the acting user is the submitter themselves.

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
            if job.pending_payload is not None:
                self._apply_pending_payload(job)
            job.status = JobStatus.PUBLISHED
            job.was_published = True
        else:
            # INITIAL or REVISION
            if (
                job.status == JobStatus.PUBLISHED_PENDING_REVISION
                and review.kind == JobReviewKind.REVISION
            ):
                self._apply_pending_payload(job)
            job.status = JobStatus.PUBLISHED
            job.was_published = True
        job = await self.job_repository.update_job(session, job)
        if review.submitted_by != acting_user_id:
            await self.notification_repository.create(
                session,
                NotificationEntity(
                    user_id=review.submitted_by,
                    type=NotificationType.JOB_REVIEW_APPROVED,
                    job_id=job.job_id,
                    job_review_id=review.review_id,
                    actor_user_id=acting_user_id,
                ),
            )
        await session.commit()
        return self.recruiting_mapper.to_job_dto(job)

    async def reject(
        self, session: AsyncSession, review_id: int, comment: str, acting_user_id: int
    ) -> JobDto:
        """Reject a pending review.

        Review-kind state machine on rejection:
        - INITIAL: posting returns to DRAFT.
        - REVISION: pending_payload is discarded and the posting stays PUBLISHED.
        - CLOSE: the close is aborted and the posting returns to PUBLISHED.
        - REOPEN: the reopen is aborted and the posting remains CLOSED.

        Also inserts a JOB_REVIEW_REJECTED notification for the review's
        submitter, unless the acting user is the submitter themselves.

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
            job.pending_payload = None
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
        if review.submitted_by != acting_user_id:
            await self.notification_repository.create(
                session,
                NotificationEntity(
                    user_id=review.submitted_by,
                    type=NotificationType.JOB_REVIEW_REJECTED,
                    job_id=job.job_id,
                    job_review_id=review.review_id,
                    actor_user_id=acting_user_id,
                ),
            )
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

    async def list_published(self, session: AsyncSession) -> list[PublicJobSummaryDto]:
        """List all PUBLISHED postings as candidate-safe card summaries.

        Serves the logged-in jobs-browse page; the projection deliberately
        carries no form/config/internal fields.

        Args:
            session (AsyncSession): Active database async session.

        Returns:
            list[PublicJobSummaryDto]: One summary per published posting.
        """
        jobs = await self.job_repository.list_published(session)
        return [self.recruiting_mapper.to_public_job_summary_dto(j) for j in jobs]

    async def list_all_jobs(self, session: AsyncSession) -> list[JobDto]:
        """List postings of every status (internal/admin view).

        Each posting is annotated with the reject_comment from its most-recent
        review when that review was a rejection, so the creator can see the
        posting was sent back and why. It's also annotated with that same
        review's reviewer_id when the review is still PENDING, so the creator
        can see who it's currently assigned to. Both fields self-clear once a
        newer review becomes the latest (or the prior one is decided).

        Args:
            session (AsyncSession): Active database async session.

        Returns:
            list[JobDto]: All postings regardless of status, each carrying
            ``last_reject_comment`` if the posting's latest review was a
            rejection, and ``reviewer_id`` if the posting's latest review is
            still open, otherwise ``None`` for either.
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
            reviewer_id = (
                latest.reviewer_id
                if latest is not None and latest.status == JobReviewStatus.PENDING
                else None
            )
            dtos.append(
                self.recruiting_mapper.to_job_dto(
                    j, last_reject_comment=comment, reviewer_id=reviewer_id
                )
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
            JobDto: The requested posting, with ``reviewer_id`` set to its
            open (PENDING) review's reviewer when one exists, otherwise
            ``None``.

        Raises:
            ValueError: If no posting with the given id exists.
        """
        job = await self._require_job(session, job_id)
        open_review = await self.job_review_repository.get_open_for_job(session, job_id)
        reviewer_id = open_review.reviewer_id if open_review is not None else None
        return self.recruiting_mapper.to_job_dto(job, reviewer_id=reviewer_id)

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

    async def get_published_job(self, session: AsyncSession, job_id: int) -> JobDto:
        """Return a posting only when it is PUBLISHED (candidate-facing view).

        Args:
            session (AsyncSession): Active database async session.
            job_id (int): The posting id.

        Returns:
            JobDto: The published posting.

        Raises:
            ValueError: If the posting is missing or not PUBLISHED.
        """
        job = await self.job_repository.get_by_job_id(session, job_id)
        if job is None or job.status != JobStatus.PUBLISHED:
            raise ValueError(f"Published job {job_id} not found")
        return self.recruiting_mapper.to_job_dto(job)

    async def get_published_job_public(
        self, session: AsyncSession, job_id: int
    ) -> PublicJobDto:
        """Return a PUBLISHED posting's candidate-safe projection.

        Same lookup/validation as ``get_published_job``, but maps through
        ``to_public_job_dto`` so internal config (screen_rules,
        pipeline_config, pending_*, last_reject_comment) never reaches the
        candidate-facing application form.

        Args:
            session (AsyncSession): Active database async session.
            job_id (int): The posting id.

        Returns:
            PublicJobDto: The published posting's candidate-safe projection.

        Raises:
            ValueError: If the posting is missing or not PUBLISHED.
        """
        job = await self.job_repository.get_by_job_id(session, job_id)
        if job is None or job.status != JobStatus.PUBLISHED:
            raise ValueError(f"Published job {job_id} not found")
        return self.recruiting_mapper.to_public_job_dto(job)
