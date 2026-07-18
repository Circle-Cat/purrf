from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.recruiting_enums import (
    ApplicationStage,
    JobStatus,
    NotificationType,
)
from backend.dto.application_dto import (
    ApplicationDto,
    ApplicationEditDto,
    ApplicationSubmitDto,
)
from backend.dto.user_context_dto import UserContextDto
from backend.entity.application_entity import ApplicationEntity
from backend.entity.application_submission_entity import ApplicationSubmissionEntity
from backend.entity.notification_entity import NotificationEntity
from backend.recruiting import cooldown, screen_rules, stage_machine
from backend.recruiting.board_service import INTERVIEW_STAGES
from backend.recruiting.pipeline_owners import normalized_owner_ids


class ApplicationService:
    """Candidate-facing application submission + auto-screening."""

    def __init__(
        self,
        application_repository,
        application_submission_repository,
        job_repository,
        users_repository,
        recruiting_mapper,
        application_assignment_repository,
        application_activity_repository,
        notification_repository,
        user_emails_repository,
        profile_writeback=None,
    ):
        """
        Args:
            application_repository (ApplicationRepository): Container data access.
            application_submission_repository (ApplicationSubmissionRepository):
                Versioned-submission data access.
            job_repository (JobRepository): Posting data access.
            users_repository (UsersRepository): Reads is_blocked.
            user_emails_repository (UserEmailsRepository): The applicant's
                contact address for screen-rule email matching.
            recruiting_mapper (RecruitingMapper): Entity→DTO conversion.
            application_assignment_repository (ApplicationAssignmentRepository):
                Used to materialize a stage's configured default assignee
                into a real assignment row when an application first lands
                there (see ``_assign_default_if_configured``).
            application_activity_repository (ApplicationActivityRepository):
                Append-only audit log; ``submit`` logs
                ``"application_submitted"`` or ``"auto_rejected"`` here on
                every call, attributed to the candidate themselves.
            notification_repository (NotificationRepository): In-app
                notification data access; ``_assign_default_if_configured``
                notifies the materialized default assignee here.
            profile_writeback (callable | None): ``async (session, user_id, dto)``
                invoked best-effort when save_to_profile is set. Defaults to a
                no-op (wired in a later task).
        """
        self.application_repository = application_repository
        self.application_submission_repository = application_submission_repository
        self.job_repository = job_repository
        self.users_repository = users_repository
        self.recruiting_mapper = recruiting_mapper
        self.application_assignment_repository = application_assignment_repository
        self.application_activity_repository = application_activity_repository
        self.notification_repository = notification_repository
        self.user_emails_repository = user_emails_repository
        self._profile_writeback = profile_writeback

    @staticmethod
    def _today():
        """Current UTC date (seam for tests)."""
        return datetime.now(timezone.utc).date()

    @staticmethod
    def _snapshot(dto) -> dict:
        """Build the immutable submission snapshot from a submit/edit DTO."""
        return {
            "personal": dto.personal,
            "education": dto.education,
            "experience": dto.experience,
            "answers": dto.answers,
        }

    @staticmethod
    def _answered(value) -> bool:
        """True when an answer is a non-empty scalar or non-empty list."""
        if value is None:
            return False
        if isinstance(value, str):
            return value.strip() != ""
        if isinstance(value, (list, tuple)):
            return len(value) > 0
        return True

    def _validate_submission(self, job, dto) -> None:
        """Enforce résumé-required and required-question answers.

        Args:
            job (JobEntity): The posting the submission is for.
            dto (ApplicationSubmitDto | ApplicationEditDto): The payload.

        Raises:
            ValueError: If a required résumé/answer is missing.
        """
        profile_config = job.profile_config or {}
        if profile_config.get("resume") == "required" and not dto.resume_object_key:
            raise ValueError("this posting requires a résumé")
        form_schema = job.form_schema or {}
        for question in form_schema.get("questions", []):
            if question.get("required") and not self._answered(
                dto.answers.get(question["id"])
            ):
                raise ValueError(f"question {question['id']} is required")

    @staticmethod
    def _strip_uncollected_resume(job, dto) -> None:
        """Drop resume keys when the posting doesn't collect a resume.

        A ``profile_config.resume == "off"`` posting treats an upload as
        prefill-only (the parser autofills the form client-side); the file
        reference must never be persisted onto the submission. Enforced
        server-side too so a direct API call can't attach one.

        Args:
            job (JobEntity): The posting the submission is for.
            dto (ApplicationSubmitDto | ApplicationEditDto): Mutated in place.
        """
        if (job.profile_config or {}).get("resume") == "off":
            dto.resume_object_key = None
            dto.resume_sha256 = None

    @staticmethod
    def _screened_stage(job, blocked, screen_action):
        """The stage a submission lands on.

        Args:
            job (JobEntity): The posting being submitted to.
            blocked (bool): Whether the applicant is blacklisted.
            screen_action (str | None): ``"reject"`` | ``"qualify"`` |
                ``"auto_hire"`` | None — the outcome of
                ``screen_rules.evaluate()`` (always None when ``blocked``,
                since a blacklist entry is evaluated first and wins
                outright).

        Returns:
            ApplicationStage: ``REJECTED`` when blocked or a ``"reject"``
                rule matched; ``HIRED`` when an ``"auto_hire"`` rule
                matched; otherwise the job's first configured pipeline
                stage (unscreened and ``"qualify"`` both land here
                identically).
        """
        if blocked or screen_action == "reject":
            return ApplicationStage.REJECTED
        if screen_action == "auto_hire":
            return ApplicationStage.HIRED
        return stage_machine.first_stage(job.pipeline_config)

    @staticmethod
    def _screened_sub_status(stage):
        """The sub_status for a just-landed stage.

        Mirrors ``BoardService.change_stage``'s rule: ``"pending"`` for a
        real configurable pipeline stage, ``None`` for a terminal stage
        (``REJECTED``/``HIRED`` have no sub-status concept).

        Args:
            stage (ApplicationStage): The stage just landed on.

        Returns:
            str | None: ``"pending"`` or ``None``.
        """
        if stage in (ApplicationStage.REJECTED, ApplicationStage.HIRED):
            return None
        return "pending"

    @staticmethod
    def _screened_tags(blocked, screen_action, screen_rule_id):
        """The tags to store for a blocked/screen-rule-rejected outcome.

        Args:
            blocked (bool): Whether the applicant is blacklisted.
            screen_action (str | None): See ``_screened_stage``.
            screen_rule_id (str | None): The matched rule's id, if any.

        Returns:
            dict | None: ``{"auto_reject": "blocked"}`` when blocked,
                ``{"auto_reject": "screen_rule", "rule_id": ...}`` when a
                ``"reject"`` rule matched, else None (the caller falls
                back to any other tag it would otherwise set, e.g. a
                cooldown ``cold_freeze`` marker).
        """
        if blocked:
            return {"auto_reject": "blocked"}
        if screen_action == "reject":
            return {"auto_reject": "screen_rule", "rule_id": screen_rule_id}
        return None

    async def submit(
        self,
        session: AsyncSession,
        current_user: UserContextDto,
        dto: ApplicationSubmitDto,
    ) -> ApplicationDto:
        """Create/land an application (or auto-screen it, or auto-reject a
        blocked user).

        Logs an ``"application_submitted"`` (or, for a blocked applicant or
        a screen-rule ``"reject"`` match, ``"auto_rejected"``) entry to the
        audit timeline on every call, attributed to the candidate
        themselves — covers a fresh submission, a reapply after cooldown,
        and a blocked/screen-rejected outcome alike. Independent of the
        blacklist check, a matching ``screen_rules`` rule can also land the
        submission on ``REJECTED`` (a ``"reject"`` match) or ``HIRED`` (an
        ``"auto_hire"`` match) with zero human review; a ``"qualify"``
        match proceeds exactly as an unscreened submission would, with a
        note added to the activity log.

        A re-apply after rejection creates a fresh application row rather
        than reusing the rejected one: prior attempts are immutable
        history, kept exactly as they were rejected (own stage, tags, and
        submission snapshots untouched), while the new attempt starts a
        brand-new version-1 submission.

        Args:
            session (AsyncSession): Active database async session.
            current_user (UserContextDto): The authenticated applicant.
            dto (ApplicationSubmitDto): The submission payload.

        Returns:
            ApplicationDto: The persisted application with its current version.

        Raises:
            ValueError: If the posting is missing or not PUBLISHED, a required
                résumé/answer is missing, or the latest existing application
                for this job is not REJECTED (an active application must be
                edited instead of resubmitted).
        """
        job = await self.job_repository.get_by_job_id(session, dto.job_id)
        if job is None or job.status != JobStatus.PUBLISHED:
            raise ValueError(f"Published job {dto.job_id} not found")
        self._validate_submission(job, dto)
        self._strip_uncollected_resume(job, dto)

        user = await self.users_repository.get_user_by_user_id(
            session, current_user.user_id
        )
        blocked = bool(user is not None and getattr(user, "is_blocked", False))
        applicant_email = (
            await self.user_emails_repository.get_contact_email(
                session, current_user.user_id
            )
            if not blocked
            else None
        )
        screen_result = (
            {"action": None, "rule_id": None}
            if blocked
            else screen_rules.evaluate(
                job.screen_rules,
                applicant_email or "",
                dto.answers,
            )
        )
        screen_action = screen_result["action"]
        screen_rule_id = screen_result["rule_id"]

        existing = await self.application_repository.get_latest_by_job_and_user(
            session, dto.job_id, current_user.user_id
        )
        if existing is not None and existing.stage != ApplicationStage.REJECTED:
            raise ValueError(
                "you already have an application for this job; edit it instead"
            )

        stage = self._screened_stage(job, blocked, screen_action)
        tags = self._screened_tags(blocked, screen_action, screen_rule_id)
        if existing is not None and tags is None and stage != ApplicationStage.HIRED:
            # Re-apply after a rejection: carry the advisory cold_freeze tag
            # when the new attempt lands inside the job's cooldown window.
            # Anchored to the prior row's last-update time (when it was moved
            # to REJECTED), not its submitted_at, which can predate it. An
            # auto_hire landing (HIRED) or an auto-reject tag supersedes it,
            # same precedence as before.
            rejected_at = (
                existing.updated_timestamp or existing.created_datetime
            ).date()
            thaw = cooldown.compute_thaw(rejected_at, job.cooldown_days)
            if cooldown.is_in_cooldown(self._today(), thaw):
                tags = {"cold_freeze": {"thaw_date": thaw.isoformat()}}

        application = await self.application_repository.create(
            session,
            ApplicationEntity(
                job_id=dto.job_id,
                user_id=current_user.user_id,
                stage=stage,
                sub_status=self._screened_sub_status(stage),
                tags=tags,
            ),
        )
        current_sub = await self._write_version(
            session, application.application_id, 1, None, dto
        )

        await self._assign_default_if_configured(
            session, application, job, current_user
        )

        if blocked:
            await self.application_activity_repository.create(
                session,
                application.application_id,
                current_user.user_id,
                "auto_rejected",
                details={"reason": "blocked"},
            )
        elif screen_action == "reject":
            await self.application_activity_repository.create(
                session,
                application.application_id,
                current_user.user_id,
                "auto_rejected",
                details={"reason": "screen_rule", "ruleId": screen_rule_id},
            )
        else:
            details = {"stage": application.stage.value}
            if screen_action == "qualify":
                details["screenQualifyRuleId"] = screen_rule_id
            elif screen_action == "auto_hire":
                details["screenAutoHireRuleId"] = screen_rule_id
            await self.application_activity_repository.create(
                session,
                application.application_id,
                current_user.user_id,
                "application_submitted",
                details=details,
            )

        if not blocked and self._profile_writeback and dto.save_to_profile:
            await self._safe_writeback(session, current_user.user_id, dto)

        await session.commit()
        editable = self._is_editable(application, job, current_sub)
        return self.recruiting_mapper.to_application_dto(
            application, current_sub, editable=editable
        )

    async def _assign_default_if_configured(
        self, session, application, job, current_user
    ):
        """Materialize a stage's configured default assignee into a real row.

        A stage's ``defaultAssigneeId`` is only a board-display fallback
        (``BoardService.get_board`` shows it on the card) until a real
        ``application_assignment`` row exists — ``My Evaluations`` and
        evaluation submit/read only see real rows. Without this, an
        application landing directly on a stage with a configured default
        (recruiter_screening on submission, or any stage after a reapply)
        would show "Assigned to: X" on the board while X's own "My
        Evaluations" stayed empty forever, since nothing else ever creates
        that row for the entry stage.

        No-ops for a non-interview stage (e.g. a blocked applicant's
        REJECTED landing), a stage with no default configured, or a job with
        no configured owner (nothing sensible to attribute ``assigned_by``
        to — mirrors the pre-existing "no owner" board-visibility gap rather
        than raising). Logs an ``"auto_assigned"`` activity entry, attributed
        to the submitting candidate, only on the path where a row is
        actually materialized.

        Args:
            session (AsyncSession): Active database async session.
            application (ApplicationEntity): The just-landed application.
            job (JobEntity): Its posting, for pipeline_config lookup.
            current_user (UserContextDto): The submitting candidate, recorded
                as the activity entry's actor.
        """
        if application.stage not in INTERVIEW_STAGES:
            return
        default_id = None
        for entry in (job.pipeline_config or {}).get("stages") or []:
            if (
                isinstance(entry, dict)
                and entry.get("stage") == application.stage.value
            ):
                default_id = entry.get("defaultAssigneeId")
                break
        if default_id is None:
            return
        owner_ids = normalized_owner_ids(job.pipeline_config)
        if not owner_ids:
            return
        await self.application_assignment_repository.upsert(
            session,
            application.application_id,
            application.stage,
            application.current_round,
            default_id,
            owner_ids[0],
        )
        await self.application_activity_repository.create(
            session,
            application.application_id,
            current_user.user_id,
            "auto_assigned",
            details={"stage": application.stage.value, "assigneeId": default_id},
        )
        await self.notification_repository.create(
            session,
            NotificationEntity(
                user_id=default_id,
                type=NotificationType.ASSIGNED_TO_EVALUATE,
                application_id=application.application_id,
                round=application.current_round,
                actor_user_id=None,
            ),
        )

    async def edit(
        self,
        session: AsyncSession,
        current_user: UserContextDto,
        application_id: int,
        dto: ApplicationEditDto,
    ) -> ApplicationDto:
        """Overwrite the current submission version while still Applied.

        Row-locks the application for the duration of the transaction so a
        concurrent owner decision (freeze/advance via ``BoardService``)
        can't interleave with this edit — without the lock, an edit could
        silently overwrite the submission a decision was already based on.
        ``_is_editable`` is evaluated after this locked load, on the
        now-current row.

        Args:
            session (AsyncSession): Active database async session.
            current_user (UserContextDto): The authenticated applicant.
            application_id (int): The application to edit.
            dto (ApplicationEditDto): The edit payload.

        Returns:
            ApplicationDto: The persisted application with its current version.

        Raises:
            ValueError: If not the owner, the application is no longer
                editable (processing has started), or a required
                résumé/answer is missing.
        """
        application = await self._load_owned(
            session, current_user, application_id, for_update=True
        )
        job = await self.job_repository.get_by_job_id(session, application.job_id)
        current_sub = await self.application_submission_repository.get_current(
            session, application_id
        )
        if not self._is_editable(application, job, current_sub):
            raise ValueError("application is locked once processing has started")
        self._validate_submission(job, dto)
        self._strip_uncollected_resume(job, dto)
        version = current_sub.version if current_sub is not None else 1
        current_sub = await self._write_version(
            session, application_id, version, current_sub, dto
        )
        if self._profile_writeback and dto.save_to_profile:
            await self._safe_writeback(session, current_user.user_id, dto)
        await session.commit()
        editable = self._is_editable(application, job, current_sub)
        return self.recruiting_mapper.to_application_dto(
            application, current_sub, editable=editable
        )

    async def get_mine(
        self, session: AsyncSession, current_user: UserContextDto, job_id: int
    ) -> ApplicationDto | None:
        """Return the caller's application for a job, or None.

        Args:
            session (AsyncSession): Active database async session.
            current_user (UserContextDto): The authenticated applicant.
            job_id (int): The posting to look up.

        Returns:
            ApplicationDto | None: The caller's application, or None if absent.
        """
        application = await self.application_repository.get_latest_by_job_and_user(
            session, job_id, current_user.user_id
        )
        if application is None:
            return None
        current_sub = await self.application_submission_repository.get_current(
            session, application.application_id
        )
        job = await self.job_repository.get_by_job_id(session, application.job_id)
        editable = self._is_editable(application, job, current_sub)
        return self.recruiting_mapper.to_application_dto(
            application, current_sub, editable=editable
        )

    async def list_mine(self, session, current_user) -> list:
        """Return every application the caller has ever submitted, any job kind.

        Args:
            session (AsyncSession): Active database async session.
            current_user (UserContextDto): The authenticated applicant.

        Returns:
            list[MyApplicationSummaryDto]: One row per application, in the
                order `ApplicationRepository.list_by_user` returns them.
        """
        rows = await self.application_repository.list_by_user(
            session, current_user.user_id
        )
        return [
            self.recruiting_mapper.to_my_application_summary_dto(application, job)
            for application, job in rows
        ]

    def _is_editable(self, application, job, current_submission) -> bool:
        """Whether the candidate may still edit: first-stage, untouched, unfrozen.

        Args:
            application (ApplicationEntity): The application container.
            job (JobEntity): The posting the application is for.
            current_submission (ApplicationSubmissionEntity | None): The
                application's current (highest) submission version.

        Returns:
            bool: True while the application sits at the job's first
                configured pipeline stage, its sub_status is still
                ``"pending"``, and the current submission is not frozen.
        """
        return (
            application.stage == stage_machine.first_stage(job.pipeline_config)
            and (application.sub_status or "pending") == "pending"
            and not (current_submission is not None and current_submission.is_frozen)
        )

    async def _load_owned(
        self, session, current_user, application_id, *, for_update: bool = False
    ):
        """Fetch an application and assert the caller owns it.

        Args:
            session (AsyncSession): Active database async session.
            current_user (UserContextDto): The authenticated applicant.
            application_id (int): The application to fetch.
            for_update (bool): When True, row-locks the application
                (``SELECT ... FOR UPDATE``) so a concurrent owner decision
                (freeze/advance) on the same application can't interleave
                with this call. ``edit`` passes True (it mutates); read-only
                callers should leave this False.

        Returns:
            ApplicationEntity: The owned application.

        Raises:
            ValueError: If missing or owned by another user.
        """
        application = await self.application_repository.get_by_id(
            session, application_id, for_update=for_update
        )
        if application is None or application.user_id != current_user.user_id:
            raise ValueError(f"application {application_id} not found")
        return application

    async def _write_version(self, session, application_id, version, current_sub, dto):
        """Overwrite the current version in place, or create version 1.

        Args:
            session (AsyncSession): Active database async session.
            application_id (int): The owning application.
            version (int): The version number to write.
            current_sub (ApplicationSubmissionEntity | None): The existing
                current version, or None to create version 1.
            dto (ApplicationSubmitDto | ApplicationEditDto): The payload.

        Returns:
            ApplicationSubmissionEntity: The persisted submission version.
        """
        snapshot = self._snapshot(dto)
        if current_sub is None:
            return await self.application_submission_repository.create(
                session,
                ApplicationSubmissionEntity(
                    application_id=application_id,
                    version=version,
                    submission=snapshot,
                    resume_object_key=dto.resume_object_key,
                    resume_sha256=dto.resume_sha256,
                ),
            )
        current_sub.submission = snapshot
        current_sub.resume_object_key = dto.resume_object_key
        current_sub.resume_sha256 = dto.resume_sha256
        return await self.application_submission_repository.update(session, current_sub)

    async def _safe_writeback(self, session, user_id, dto):
        """Best-effort Profile write-back; swallow failures.

        Args:
            session (AsyncSession): Active database async session.
            user_id (int): The applicant whose profile may be updated.
            dto (ApplicationSubmitDto | ApplicationEditDto): The payload.
        """
        try:
            await self._profile_writeback(session, user_id, dto)
        except Exception:  # noqa: BLE001 - application is source of truth; never fail submit
            pass
