from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.mentorship_enums import ApprovalStatus
from backend.common.recruiting_enums import ApplicationStage
from backend.dto.application_dto import ApplicationBoardCardDto, ApplicationDto, ApplicationSubmitDto
from backend.entity.application_entity import ApplicationEntity
from backend.entity.mentorship_round_participants_entity import MentorshipRoundParticipantsEntity
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
        participants_repository,
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
            participants_repository: Data-access layer for MentorshipRoundParticipantsEntity;
                used to idempotently enrol hired candidates.
        """
        self.application_repository = application_repository
        self.job_repository = job_repository
        self.mentorship_round_repository = mentorship_round_repository
        self.users_repository = users_repository
        self.recruiting_mapper = recruiting_mapper
        self.experience_repository = experience_repository
        self.participants_repository = participants_repository

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

    async def advance(
        self,
        session: AsyncSession,
        application_id: int,
        target_stage: ApplicationStage,
        now: datetime,
    ) -> ApplicationDto:
        """Manually advance an application to HIRED or REJECTED.

        HIRED idempotently enrolls the candidate into mentorship_round_participants
        (creates an entry with SIGNED_UP status if not already present), then sets
        the stage to HIRED. REJECTED records the current round and timestamp for
        re-application cooldown calculation.

        Args:
            session (AsyncSession): Active database async session.
            application_id (int): Identifier of the application to advance.
            target_stage (ApplicationStage): Must be HIRED or REJECTED.
            now (datetime): Current UTC timestamp; stamped on rejection.

        Returns:
            ApplicationDto: The updated application.

        Raises:
            ValueError: If the application does not exist.
            ValueError: If target_stage is not HIRED or REJECTED.
        """
        app = await self.application_repository.get_by_id(session, application_id)
        if app is None:
            raise ValueError(f"Application {application_id} not found")

        if target_stage == ApplicationStage.HIRED:
            job = await self.job_repository.get_by_job_id(session, app.job_id)
            existing = await self.participants_repository.get_by_user_id_and_round_id(
                session, app.user_id, app.round_id
            )
            if existing is None:
                participant = MentorshipRoundParticipantsEntity(
                    user_id=app.user_id,
                    round_id=app.round_id,
                    participant_role=job.mentorship_role,
                    approval_status=ApprovalStatus.SIGNED_UP,
                )
                await self.participants_repository.upsert_participant(session, participant)
            app.stage = ApplicationStage.HIRED
        elif target_stage == ApplicationStage.REJECTED:
            app.stage = ApplicationStage.REJECTED
            app.rejected_round_id = app.round_id
            app.rejected_at = now
        else:
            raise ValueError(f"Unsupported target stage for MVP: {target_stage}")

        app = await self.application_repository.update_application(session, app)
        await session.commit()
        return self.recruiting_mapper.to_application_dto(app)

    async def list_board(
        self, session: AsyncSession, job_id: int, now: datetime
    ) -> list[ApplicationBoardCardDto]:
        """List a job's active applications as board cards with a freeze annotation.

        For each active application, computes whether the candidate is inside a
        re-application freeze window based on their most recent rejection.

        Args:
            session (AsyncSession): Active database async session.
            job_id (int): Identifier of the job whose board to return.
            now (datetime): Current UTC timestamp used to evaluate active freeze windows.

        Returns:
            list[ApplicationBoardCardDto]: Board cards with optional freeze_until timestamps.
        """
        apps = await self.application_repository.list_active_by_job(session, job_id)
        cards: list[ApplicationBoardCardDto] = []
        for app in apps:
            freeze_until = await self._compute_freeze_until(session, app, job_id, now)
            cards.append(self.recruiting_mapper.to_board_card_dto(app, freeze_until))
        return cards

    async def _compute_freeze_until(
        self, session: AsyncSession, app: ApplicationEntity, job_id: int, now: datetime
    ) -> datetime | None:
        """Compute the freeze_until timestamp for a candidate's active application.

        Looks up the most recent REJECTED application for the same (user, job) pair.
        If one exists and its rejection round has a reapply_freeze_days value, returns
        the end of the freeze window if it has not yet elapsed, otherwise None.

        Args:
            session (AsyncSession): Active database async session.
            app (ApplicationEntity): The active application being evaluated.
            job_id (int): Identifier of the job posting.
            now (datetime): Current UTC timestamp for freeze-window comparison.

        Returns:
            datetime | None: The freeze expiry if still active, or None.
        """
        prior = await self.application_repository.get_latest_rejected(
            session, app.user_id, job_id
        )
        if prior is None or prior.application_id == app.application_id or prior.rejected_at is None:
            return None
        round_entity = await self.mentorship_round_repository.get_by_round_id(
            session, prior.rejected_round_id
        )
        if round_entity is None:
            return None
        freeze_until = prior.rejected_at + timedelta(days=round_entity.reapply_freeze_days)
        return freeze_until if freeze_until > now else None
