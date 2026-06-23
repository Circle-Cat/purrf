from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.recruiting_enums import ApplicationStage
from backend.dto.application_dto import ApplicationDto, ApplicationSubmitDto
from backend.entity.application_entity import ApplicationEntity
from backend.repository.application_repository import ApplicationRepository
from backend.repository.experience_repository import ExperienceRepository
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
        experience_repository: ExperienceRepository,
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
            experience_repository (ExperienceRepository): Data-access layer for ExperienceEntity;
                used to read candidate education and work history for the view snapshot.
        """
        self.application_repository = application_repository
        self.job_repository = job_repository
        self.mentorship_round_repository = mentorship_round_repository
        self.users_repository = users_repository
        self.recruiting_mapper = recruiting_mapper
        self.experience_repository = experience_repository

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

    async def mark_viewed(self, session: AsyncSession, application_id: int) -> ApplicationDto:
        """Flip is_viewed on first screener open and freeze a snapshot. Idempotent.

        On the first call, sets ``is_viewed=True`` and writes a ``snapshot`` dict capturing
        the candidate's user profile, experience (education + work history), and form answers
        at the moment of first view. Subsequent calls return the existing DTO unchanged without
        overwriting the snapshot.

        Args:
            session (AsyncSession): Active database async session.
            application_id (int): Identifier of the application to mark as viewed.

        Returns:
            ApplicationDto: The updated (or unchanged) application.

        Raises:
            ValueError: If the application does not exist.
        """
        app = await self.application_repository.get_by_id(session, application_id)
        if app is None:
            raise ValueError(f"Application {application_id} not found")
        if app.is_viewed:
            return self.recruiting_mapper.to_application_dto(app)

        user = await self.users_repository.get_user_by_user_id(session, app.user_id)
        experience = await self.experience_repository.get_experience_by_user_id(
            session, app.user_id
        )
        app.is_viewed = True
        app.snapshot = {
            "user": {
                "user_id": user.user_id,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "primary_email": user.primary_email,
            } if user else None,
            "experience": {
                "education": experience.education if experience else None,
                "work_history": experience.work_history if experience else None,
            },
            "form_answers": app.form_answers,
        }
        app = await self.application_repository.update_application(session, app)
        await session.commit()
        return self.recruiting_mapper.to_application_dto(app)
