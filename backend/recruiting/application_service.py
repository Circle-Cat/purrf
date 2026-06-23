from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.recruiting_enums import ApplicationStage
from backend.dto.application_dto import ApplicationDto, ApplicationSubmitDto
from backend.entity.application_entity import ApplicationEntity
from backend.repository.application_repository import ApplicationRepository
from backend.repository.job_repository import JobRepository
from backend.repository.mentorship_round_repository import MentorshipRoundRepository
from backend.recruiting.recruiting_mapper import RecruitingMapper


class ApplicationService:
    """Candidate application lifecycle: submit, view-lock, advance."""

    def __init__(
        self,
        application_repository: ApplicationRepository,
        job_repository: JobRepository,
        mentorship_round_repository: MentorshipRoundRepository,
        users_repository,
        recruiting_mapper: RecruitingMapper,
    ):
        """
        Initialise the service with its repositories and mapper.

        Args:
            application_repository (ApplicationRepository): Data-access layer for ApplicationEntity.
            job_repository (JobRepository): Data-access layer for JobEntity.
            mentorship_round_repository (MentorshipRoundRepository): Data-access layer for
                MentorshipRoundEntity; used to resolve the open application round.
            users_repository: Data-access layer for UsersEntity.
            recruiting_mapper (RecruitingMapper): Entity-to-DTO converter.
        """
        self.application_repository = application_repository
        self.job_repository = job_repository
        self.mentorship_round_repository = mentorship_round_repository
        self.users_repository = users_repository
        self.recruiting_mapper = recruiting_mapper

    async def submit(
        self,
        session: AsyncSession,
        job_id: int,
        user_id: int,
        dto: ApplicationSubmitDto,
        now: datetime,
    ) -> ApplicationDto:
        """Submit a candidate application for a posting.

        Resolves the open mentorship-round for the posting's role, then creates
        the application entity. A blocked user is auto-rejected (stage REJECTED,
        with rejected_round_id and rejected_at stamped). All other users land at
        RECRUITER_SCREENING. The session is committed before returning.

        Args:
            session (AsyncSession): Active database async session.
            job_id (int): Identifier of the job posting to apply to.
            user_id (int): Identifier of the candidate submitting the application.
            dto (ApplicationSubmitDto): Submitted form answers.
            now (datetime): Current UTC timestamp used for rejection timestamps.

        Returns:
            ApplicationDto: The newly created application.

        Raises:
            ValueError: If the job does not exist.
            ValueError: If no open application round exists for the posting's role.
        """
        job = await self.job_repository.get_by_job_id(session, job_id)
        if job is None:
            raise ValueError(f"Job {job_id} not found")

        open_round = await self.mentorship_round_repository.get_open_application_round(
            session, job.mentorship_role, now
        )
        if open_round is None:
            raise ValueError("No open application round for this posting")

        user = await self.users_repository.get_user_by_user_id(session, user_id)
        is_blocked = bool(user and user.is_blocked)

        stage = ApplicationStage.REJECTED if is_blocked else ApplicationStage.RECRUITER_SCREENING
        application = ApplicationEntity(
            user_id=user_id,
            job_id=job_id,
            round_id=open_round.round_id,
            stage=stage,
            form_answers=dto.form_answers,
            is_viewed=False,
        )
        if is_blocked:
            application.rejected_round_id = open_round.round_id
            application.rejected_at = now

        application = await self.application_repository.create_application(session, application)
        await session.commit()
        return self.recruiting_mapper.to_application_dto(application)
