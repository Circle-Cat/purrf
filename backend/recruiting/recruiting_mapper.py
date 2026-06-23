from datetime import datetime
from backend.entity.job_entity import JobEntity
from backend.entity.application_entity import ApplicationEntity
from backend.dto.job_dto import JobDto
from backend.dto.application_dto import ApplicationDto, ApplicationBoardCardDto


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
        )

    def to_application_dto(self, app: ApplicationEntity) -> ApplicationDto:
        """Map an ApplicationEntity to an ApplicationDto."""
        return ApplicationDto(
            id=app.application_id,
            user_id=app.user_id,
            job_id=app.job_id,
            round_id=app.round_id,
            stage=app.stage,
            form_answers=app.form_answers,
            snapshot=app.snapshot,
            is_viewed=app.is_viewed,
        )

    def to_board_card_dto(
        self, app: ApplicationEntity, freeze_until: datetime | None
    ) -> ApplicationBoardCardDto:
        """Map an application to a board card with a freeze annotation."""
        return ApplicationBoardCardDto(
            id=app.application_id,
            user_id=app.user_id,
            job_id=app.job_id,
            round_id=app.round_id,
            stage=app.stage,
            form_answers=app.form_answers,
            snapshot=app.snapshot,
            is_viewed=app.is_viewed,
            freeze_until=freeze_until,
        )
