from sqlalchemy.ext.asyncio import AsyncSession

from backend.dto.board_dto import ApplicationDetailDto, BoardCardDto, BoardJobDto
from backend.dto.user_context_dto import UserContextDto
from backend.entity.job_entity import JobEntity
from backend.recruiting import stage_machine
from backend.recruiting.pipeline_owners import normalized_owner_ids


class BoardService:
    """Owner-facing reads for the recruiting application board (PR2).

    Every read here is row-level owner-gated against a job's
    ``pipeline_config`` owner ids (see ``pipeline_owners.normalized_owner_ids``)
    rather than an enum permission — visibility is "did you configure
    yourself as an owner of this posting", not a role.
    """

    def __init__(
        self,
        job_repository,
        application_repository,
        application_submission_repository,
        users_repository,
        recruiting_mapper,
    ):
        """
        Args:
            job_repository (JobRepository): Posting data access.
            application_repository (ApplicationRepository): Container data access.
            application_submission_repository (ApplicationSubmissionRepository):
                Versioned-submission data access.
            users_repository (UsersRepository): Applicant lookups for the
                detail view.
            recruiting_mapper (RecruitingMapper): Entity->DTO conversion.
        """
        self.job_repository = job_repository
        self.application_repository = application_repository
        self.application_submission_repository = application_submission_repository
        self.users_repository = users_repository
        self.recruiting_mapper = recruiting_mapper

    async def list_my_jobs(
        self, session: AsyncSession, current_user: UserContextDto
    ) -> list[BoardJobDto]:
        """List jobs the caller owns, for the board's job switcher.

        Fetches every job via the same list-all repository call
        ``JobService.list_all_jobs`` uses, and filters ownership in Python.
        That's fine at dogfood scale (a handful of postings); an
        owner-indexed query would be worth adding if the job table grows.

        Args:
            session (AsyncSession): Active database async session.
            current_user (UserContextDto): The authenticated caller.

        Returns:
            list[BoardJobDto]: Jobs the caller owns, each with its
                configured pipeline stages in global order.
        """
        jobs = await self.job_repository.list_all(session)
        return [
            BoardJobDto(
                id=job.job_id,
                title=job.title,
                kind=job.kind,
                stages=[
                    stage.value
                    for stage in stage_machine.configured_stages(job.pipeline_config)
                ],
            )
            for job in jobs
            if current_user.user_id in normalized_owner_ids(job.pipeline_config)
        ]

    async def _require_owner(
        self, session: AsyncSession, current_user: UserContextDto, job_id: int
    ) -> JobEntity:
        """Load a job and assert the caller is one of its configured owners.

        Args:
            session (AsyncSession): Active database async session.
            current_user (UserContextDto): The authenticated caller.
            job_id (int): The posting to load.

        Returns:
            JobEntity: The loaded job.

        Raises:
            ValueError: If the job is missing or the caller is not an owner.
        """
        job = await self.job_repository.get_by_job_id(session, job_id)
        if job is None or current_user.user_id not in normalized_owner_ids(
            job.pipeline_config
        ):
            raise ValueError("you are not an owner of this job")
        return job

    async def get_board(
        self, session: AsyncSession, current_user: UserContextDto, job_id: int
    ) -> dict[str, list[BoardCardDto]]:
        """Return a job's applications grouped by stage, for the board columns.

        Args:
            session (AsyncSession): Active database async session.
            current_user (UserContextDto): The authenticated caller.
            job_id (int): The posting whose board to load.

        Returns:
            dict[str, list[BoardCardDto]]: Applicant cards keyed by the
                application's stage value.

        Raises:
            ValueError: If the caller is not an owner of the job.
        """
        await self._require_owner(session, current_user, job_id)
        rows = await self.application_repository.list_by_job(session, job_id)
        board: dict[str, list[BoardCardDto]] = {}
        for application, user in rows:
            card = self.recruiting_mapper.to_board_card_dto(application, user)
            board.setdefault(application.stage.value, []).append(card)
        return board

    async def get_application_detail(
        self,
        session: AsyncSession,
        current_user: UserContextDto,
        application_id: int,
    ) -> ApplicationDetailDto:
        """Return the owner-facing full view of one application.

        Args:
            session (AsyncSession): Active database async session.
            current_user (UserContextDto): The authenticated caller.
            application_id (int): The application to load.

        Returns:
            ApplicationDetailDto: The application, applicant identity,
                résumé availability, and the job's live form schema (so the
                dialog can label answers by question id).

        Raises:
            ValueError: If the application is missing, or the caller is not
                an owner of the application's job.
        """
        application = await self.application_repository.get_by_id(
            session, application_id
        )
        if application is None:
            raise ValueError(f"application {application_id} not found")
        job = await self._require_owner(session, current_user, application.job_id)
        user = await self.users_repository.get_user_by_user_id(
            session, application.user_id
        )
        current_sub = await self.application_submission_repository.get_current(
            session, application_id
        )
        application_dto = self.recruiting_mapper.to_application_dto(
            application, current_sub
        )
        return ApplicationDetailDto(
            application=application_dto,
            applicant_name=(
                f"{user.first_name} {user.last_name}".strip()
                if user is not None
                else ""
            ),
            applicant_email=user.primary_email if user is not None else "",
            resume_available=bool(
                current_sub is not None and current_sub.resume_object_key
            ),
            form_schema=job.form_schema,
        )
