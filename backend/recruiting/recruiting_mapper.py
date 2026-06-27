from backend.entity.job_entity import JobEntity
from backend.dto.job_dto import JobDto


class RecruitingMapper:
    """Converts recruiting entities to DTOs."""

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
