from backend.entity.application_entity import ApplicationEntity
from backend.entity.job_entity import JobEntity
from backend.entity.job_review_entity import JobReviewEntity
from backend.entity.users_entity import UsersEntity
from backend.dto.board_dto import BoardCardDto
from backend.dto.job_dto import JobDto, PublicJobDto, PublicJobSummaryDto
from backend.dto.job_review_dto import ApproverDto, JobReviewDto


class RecruitingMapper:
    """Converts recruiting entities to DTOs."""

    def to_approver_dto(self, user: UsersEntity, email: str) -> ApproverDto:
        """Map a user to an ApproverDto (full name + contact email).

        Args:
            user (UsersEntity): The approver row.
            email (str): The user's contact address from user_emails (see
                ``UserEmailsRepository.get_contact_emails_by_user_ids``);
                empty when they have none.

        Returns:
            ApproverDto: The approver projection.
        """
        return ApproverDto(
            user_id=user.user_id,
            name=f"{user.first_name} {user.last_name}",
            email=email,
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
        self,
        job: JobEntity,
        last_reject_comment: str | None = None,
        last_reject_kind: str | None = None,
        reviewer_id: int | None = None,
    ) -> JobDto:
        """Map a JobEntity to a JobDto.

        Args:
            job (JobEntity): The posting entity to convert.
            last_reject_comment (str | None): The reject_comment from that
                job's most-recent review if it was a rejection, otherwise
                ``None``. Serialised as ``lastRejectComment`` in API responses.
            last_reject_kind (str | None): The ``JobReviewKind`` value
                (``"initial"``/``"revision"``/``"close"``/``"reopen"``) of
                that same most-recent rejected review, or ``None``.
                Serialised as ``lastRejectKind``.
            reviewer_id (int | None): The user_id of the posting's currently
                assigned reviewer, when it has an open (PENDING) review
                cycle, otherwise ``None``. Serialised as ``reviewerId``.

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
            pending_payload=job.pending_payload,
            last_reject_comment=last_reject_comment,
            last_reject_kind=last_reject_kind,
            was_published=job.was_published or False,
            cooldown_days=job.cooldown_days,
            reviewer_id=reviewer_id,
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

    def to_public_job_summary_dto(self, job: JobEntity) -> PublicJobSummaryDto:
        """Map a JobEntity to the candidate-safe list-card summary.

        Args:
            job (JobEntity): The published posting entity to convert.

        Returns:
            PublicJobSummaryDto: id/title/kind/description only.
        """
        return PublicJobSummaryDto(
            id=job.job_id,
            title=job.title,
            kind=job.kind,
            description=job.description,
        )

    def to_board_card_dto(
        self,
        application: ApplicationEntity,
        user: UsersEntity,
        reviewer_name: str | None = None,
        applicant_email: str = "",
    ) -> BoardCardDto:
        """Map an application + its joined applicant to a board card.

        Args:
            application (ApplicationEntity): The application to project.
            user (UsersEntity): The applicant, joined by user_id.
            reviewer_name (str | None): The resolved interviewer name for
                this card's current stage+round (see
                ``BoardService.get_board``), or None when there is no
                reviewer to show (either the stage isn't an interview stage,
                or nobody is assigned yet).
            applicant_email (str): The applicant's contact address from
                user_emails; empty when they have none.

        Returns:
            BoardCardDto: The board's applicant-card projection.
        """
        return BoardCardDto(
            id=application.application_id,
            applicant_name=f"{user.first_name} {user.last_name}".strip(),
            applicant_email=applicant_email,
            stage=application.stage,
            sub_status=application.sub_status,
            tags=application.tags,
            applied_at=application.created_datetime,
            round=application.current_round,
            is_blocked=bool(user.is_blocked),
            reviewer_name=reviewer_name,
        )

    def to_application_dto(self, application, current_submission=None, editable=False):
        """Map an application (+ its current submission version) to a DTO.

        Args:
            application (ApplicationEntity): The application container.
            current_submission (ApplicationSubmissionEntity | None): Highest
                version, or None if not yet written.
            editable (bool): Whether the candidate may still edit this
                application (see ``ApplicationService._is_editable``).

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
            editable=editable,
            current_round=application.current_round,
        )

    def to_my_application_summary_dto(self, application, job):
        """Map an (application, job) pair to the caller's own-application summary row.

        Args:
            application (ApplicationEntity): The candidate's application.
            job (JobEntity): The posting it was submitted to.

        Returns:
            MyApplicationSummaryDto: The response row.
        """
        from backend.dto.application_dto import MyApplicationSummaryDto

        return MyApplicationSummaryDto(
            application_id=application.application_id,
            job_id=application.job_id,
            job_title=job.title,
            job_kind=job.kind,
            mentorship_role=job.mentorship_role,
            stage=application.stage,
        )
