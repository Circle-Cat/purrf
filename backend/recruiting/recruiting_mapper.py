from backend.entity.job_entity import JobEntity
from backend.entity.users_entity import UsersEntity
from backend.dto.job_dto import JobDto
from backend.dto.job_review_dto import ApproverDto


class RecruitingMapper:
    """Converts recruiting entities to DTOs."""

    def to_approver_dto(self, user: UsersEntity) -> ApproverDto:
        """Map a user to an ApproverDto (full name + primary email)."""
        return ApproverDto(
            user_id=user.user_id,
            name=f"{user.first_name} {user.last_name}",
            email=user.primary_email,
        )

    def to_job_dto(self, job: JobEntity) -> JobDto:
        """Map a JobEntity to a JobDto."""
        return JobDto(
            id=job.job_id,
            title=job.title,
            description=job.description,
            kind=job.kind,
            mentorship_role=job.mentorship_role,
            status=job.status,
            form_schema=job.form_schema,
            pipeline_config=job.pipeline_config,
            pending_form_schema=job.pending_form_schema,
            pending_pipeline_config=job.pending_pipeline_config,
        )
