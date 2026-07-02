from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.recruiting_enums import ApplicationStage, JobStatus
from backend.dto.application_dto import (
    ApplicationDto,
    ApplicationEditDto,
    ApplicationSubmitDto,
)
from backend.dto.user_context_dto import UserContextDto
from backend.entity.application_entity import ApplicationEntity
from backend.entity.application_submission_entity import ApplicationSubmissionEntity
from backend.recruiting import cooldown, stage_machine


class ApplicationService:
    """Candidate-facing application submission + auto-screening."""

    def __init__(
        self,
        application_repository,
        application_submission_repository,
        job_repository,
        users_repository,
        recruiting_mapper,
        profile_writeback=None,
    ):
        """
        Args:
            application_repository (ApplicationRepository): Container data access.
            application_submission_repository (ApplicationSubmissionRepository):
                Versioned-submission data access.
            job_repository (JobRepository): Posting data access.
            users_repository (UsersRepository): Reads is_blocked.
            recruiting_mapper (RecruitingMapper): Entity→DTO conversion.
            profile_writeback (callable | None): ``async (session, user_id, dto)``
                invoked best-effort when save_to_profile is set. Defaults to a
                no-op (wired in a later task).
        """
        self.application_repository = application_repository
        self.application_submission_repository = application_submission_repository
        self.job_repository = job_repository
        self.users_repository = users_repository
        self.recruiting_mapper = recruiting_mapper
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

    async def submit(
        self,
        session: AsyncSession,
        current_user: UserContextDto,
        dto: ApplicationSubmitDto,
    ) -> ApplicationDto:
        """Create/land an application at Applied (or auto-reject a blocked user).

        Args:
            session (AsyncSession): Active database async session.
            current_user (UserContextDto): The authenticated applicant.
            dto (ApplicationSubmitDto): The submission payload.

        Returns:
            ApplicationDto: The persisted application with its current version.

        Raises:
            ValueError: If the posting is missing or not PUBLISHED, a required
                résumé/answer is missing, or an existing application is not a
                REJECTED terminal eligible for re-application.
        """
        job = await self.job_repository.get_by_job_id(session, dto.job_id)
        if job is None or job.status != JobStatus.PUBLISHED:
            raise ValueError(f"Published job {dto.job_id} not found")
        self._validate_submission(job, dto)

        user = await self.users_repository.get_user_by_user_id(
            session, current_user.user_id
        )
        blocked = bool(user is not None and getattr(user, "is_blocked", False))

        existing = await self.application_repository.get_by_job_and_user(
            session, dto.job_id, current_user.user_id
        )

        if existing is None:
            application = await self.application_repository.create(
                session,
                ApplicationEntity(
                    job_id=dto.job_id,
                    user_id=current_user.user_id,
                    stage=(
                        ApplicationStage.REJECTED
                        if blocked
                        else stage_machine.first_stage(job.pipeline_config)
                    ),
                    sub_status=None if blocked else "pending",
                    tags={"auto_reject": "blocked"} if blocked else None,
                ),
            )
            current_sub = await self._write_version(
                session, application.application_id, 1, None, dto
            )
        elif blocked:
            existing.stage = ApplicationStage.REJECTED
            existing.tags = {"auto_reject": "blocked"}
            application = await self.application_repository.update(session, existing)
            current_sub = await self.application_submission_repository.get_current(
                session, application.application_id
            )
            version = current_sub.version if current_sub is not None else 1
            current_sub = await self._write_version(
                session, application.application_id, version, current_sub, dto
            )
        else:
            prior = await self.application_submission_repository.get_current(
                session, existing.application_id
            )
            if existing.stage != ApplicationStage.REJECTED or prior is None:
                raise ValueError(
                    "you already have an application for this job; edit it instead"
                )
            # Freeze the prior attempt so its snapshot survives for the diff.
            prior.is_frozen = True
            await self.application_submission_repository.update(session, prior)

            applied_at = (
                existing.created_datetime or datetime.now(timezone.utc)
            ).date()
            # Use the application container's last-update time (when it was
            # moved to REJECTED), not the frozen submission's submitted_at —
            # for fixed-cooldown (non-ACTIVITY) jobs the thaw is anchored to
            # the actual rejection moment, which submitted_at can predate.
            rejected_at = (
                existing.updated_timestamp or existing.created_datetime
            ).date()
            thaw = cooldown.compute_thaw(
                job.kind, applied_at, rejected_at, job.cooldown_days
            )
            tags = (
                {"cold_freeze": {"thaw_date": thaw.isoformat()}}
                if cooldown.is_in_cooldown(self._today(), thaw)
                else None
            )
            existing.stage = stage_machine.first_stage(job.pipeline_config)
            existing.sub_status = "pending"
            existing.tags = tags
            application = await self.application_repository.update(session, existing)
            current_sub = await self.application_submission_repository.create(
                session,
                ApplicationSubmissionEntity(
                    application_id=application.application_id,
                    version=prior.version + 1,
                    submission=self._snapshot(dto),
                    resume_object_key=dto.resume_object_key,
                    resume_sha256=dto.resume_sha256,
                ),
            )

        if not blocked and self._profile_writeback and dto.save_to_profile:
            await self._safe_writeback(session, current_user.user_id, dto)

        await session.commit()
        editable = self._is_editable(application, job, current_sub)
        return self.recruiting_mapper.to_application_dto(
            application, current_sub, editable=editable
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
        application = await self.application_repository.get_by_job_and_user(
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
