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
            ValueError: If the posting is missing or not PUBLISHED, or a
                required résumé/answer is missing.
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
                        else ApplicationStage.APPLIED
                    ),
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
            # Only a re-application after a REJECTED terminal is allowed; the
            # re-apply branch (new version + cold-freeze tag) is added in Task 8.
            raise ValueError(
                "you already have an application for this job; edit it instead"
            )

        if not blocked and self._profile_writeback and dto.save_to_profile:
            await self._safe_writeback(session, current_user.user_id, dto)

        return self.recruiting_mapper.to_application_dto(application, current_sub)

    async def edit(
        self,
        session: AsyncSession,
        current_user: UserContextDto,
        application_id: int,
        dto: ApplicationEditDto,
    ) -> ApplicationDto:
        """Overwrite the current submission version while still Applied.

        Args:
            session (AsyncSession): Active database async session.
            current_user (UserContextDto): The authenticated applicant.
            application_id (int): The application to edit.
            dto (ApplicationEditDto): The edit payload.

        Returns:
            ApplicationDto: The persisted application with its current version.

        Raises:
            ValueError: If not the owner, the application has left Applied, or
                a required résumé/answer is missing.
        """
        application = await self._load_owned(session, current_user, application_id)
        if application.stage != ApplicationStage.APPLIED:
            raise ValueError(
                "application is locked; editing is only allowed while Applied"
            )
        job = await self.job_repository.get_by_job_id(session, application.job_id)
        self._validate_submission(job, dto)
        current_sub = await self.application_submission_repository.get_current(
            session, application_id
        )
        version = current_sub.version if current_sub is not None else 1
        current_sub = await self._write_version(
            session, application_id, version, current_sub, dto
        )
        if self._profile_writeback and dto.save_to_profile:
            await self._safe_writeback(session, current_user.user_id, dto)
        return self.recruiting_mapper.to_application_dto(application, current_sub)

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
        return self.recruiting_mapper.to_application_dto(application, current_sub)

    async def _load_owned(self, session, current_user, application_id):
        """Fetch an application and assert the caller owns it.

        Args:
            session (AsyncSession): Active database async session.
            current_user (UserContextDto): The authenticated applicant.
            application_id (int): The application to fetch.

        Returns:
            ApplicationEntity: The owned application.

        Raises:
            ValueError: If missing or owned by another user.
        """
        application = await self.application_repository.get_by_id(
            session, application_id
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
