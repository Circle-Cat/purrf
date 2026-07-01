from backend.entity.job_entity import JobEntity
from backend.entity.job_review_entity import JobReviewEntity
from backend.entity.users_entity import UsersEntity
from backend.dto.job_dto import JobDto, PublicJobDto
from backend.dto.job_review_dto import ApproverDto, JobReviewDto


class RecruitingMapper:
    """Converts recruiting entities to DTOs."""

    def to_approver_dto(self, user: UsersEntity) -> ApproverDto:
        """Map a user to an ApproverDto (full name + primary email)."""
        return ApproverDto(
            user_id=user.user_id,
            name=f"{user.first_name} {user.last_name}",
            email=user.primary_email,
        )

    def to_job_review_dto(
        self, review: JobReviewEntity, job_title: str | None = None
    ) -> JobReviewDto:
        """Map a JobReviewEntity to a JobReviewDto, optionally including the posting title.

        Args:
            review (JobReviewEntity): The review entity to convert.
            job_title (str | None): Title of the associated job posting, when
                available. Serialised as ``jobTitle`` in API responses.

        Returns:
            JobReviewDto: The mapped DTO with ``job_title`` set if provided.
        """
        dto = JobReviewDto.model_validate(review)
        dto.job_title = job_title
        return dto

    def to_job_dto(
        self, job: JobEntity, last_reject_comment: str | None = None
    ) -> JobDto:
        """Map a JobEntity to a JobDto.

        Args:
            job (JobEntity): The posting entity to convert.
            last_reject_comment (str | None): The reject_comment from that
                job's most-recent review if it was a rejection, otherwise
                ``None``. Serialised as ``lastRejectComment`` in API responses.

        Returns:
            JobDto: The mapped DTO.
        """
        return JobDto(
            id=job.job_id,
            title=job.title,
            description=job.description,
            kind=job.kind,
            mentorship_role=job.mentorship_role,
            status=job.status,
            form_schema=job.form_schema,
            pipeline_config=job.pipeline_config,
            screen_rules=job.screen_rules,
            profile_config=job.profile_config,
            pending_form_schema=job.pending_form_schema,
            pending_pipeline_config=job.pending_pipeline_config,
            pending_profile_config=job.pending_profile_config,
            last_reject_comment=last_reject_comment,
            was_published=job.was_published or False,
            cooldown_days=job.cooldown_days,
        )

    def to_public_job_dto(self, job: JobEntity) -> PublicJobDto:
        """Map a JobEntity to the candidate-safe PublicJobDto.

        Only exposes the fields an applicant's form needs: maps the *live*
        (published) ``form_schema``/``profile_config`` — never the
        ``pending_*`` variants — and omits ``screen_rules``,
        ``pipeline_config``, and ``last_reject_comment`` entirely.

        Args:
            job (JobEntity): The published posting entity to convert.

        Returns:
            PublicJobDto: The candidate-facing projection.
        """
        return PublicJobDto(
            id=job.job_id,
            title=job.title,
            description=job.description,
            kind=job.kind,
            mentorship_role=job.mentorship_role,
            form_schema=job.form_schema,
            profile_config=job.profile_config,
        )

    def to_application_dto(self, application, current_submission=None):
        """Map an application (+ its current submission version) to a DTO.

        Args:
            application (ApplicationEntity): The application container.
            current_submission (ApplicationSubmissionEntity | None): Highest
                version, or None if not yet written.

        Returns:
            ApplicationDto: The response DTO.
        """
        from backend.dto.application_dto import ApplicationDto, ApplicationSubmissionDto

        current = (
            ApplicationSubmissionDto(
                version=current_submission.version,
                # Mapped-column default (False) only applies on flush; a
                # freshly-constructed, not-yet-flushed entity has None here.
                is_frozen=bool(current_submission.is_frozen),
                submission=current_submission.submission,
                resume_object_key=current_submission.resume_object_key,
                resume_sha256=current_submission.resume_sha256,
                submitted_at=current_submission.submitted_at,
            )
            if current_submission is not None
            else None
        )
        return ApplicationDto(
            id=application.application_id,
            job_id=application.job_id,
            user_id=application.user_id,
            stage=application.stage,
            sub_status=application.sub_status,
            tags=application.tags,
            current=current,
        )
