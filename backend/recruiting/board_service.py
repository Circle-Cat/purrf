from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from backend.dto.application_dto import ApplicationDto
from backend.dto.board_dto import (
    ApplicationDetailDto,
    BlacklistDto,
    BoardCardDto,
    BoardJobDto,
    StageChangeDto,
    SubStatusChangeDto,
)
from backend.dto.user_context_dto import UserContextDto
from backend.common.recruiting_enums import ApplicationStage
from backend.entity.application_entity import ApplicationEntity
from backend.entity.job_entity import JobEntity
from backend.recruiting import stage_machine
from backend.recruiting.pipeline_owners import normalized_owner_ids


class BoardService:
    """Owner-facing reads for the recruiting application board (PR2).

    Every read here is row-level owner-gated against a job's
    ``pipeline_config`` owner ids (see ``pipeline_owners.normalized_owner_ids``)
    rather than an enum permission — visibility is "did you configure
    yourself as an owner of this posting", not a role. ``blacklist`` is the
    one exception: it's an org-level sanction gated only by the
    ``RECRUITING_BLACKLIST_WRITE`` permission at the route, not by job
    ownership (see its docstring).
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
                application's stage value. Stages with zero cards are
                absent keys — the frontend must ``.get(stage, [])``.

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

    async def _load_owned_application(
        self,
        session: AsyncSession,
        current_user: UserContextDto,
        application_id: int,
        *,
        for_update: bool = False,
    ) -> tuple[ApplicationEntity, JobEntity]:
        """Load an application and assert the caller owns its job.

        Args:
            session (AsyncSession): Active database async session.
            current_user (UserContextDto): The authenticated caller.
            application_id (int): The application to load.
            for_update (bool): When True, row-locks the application (``SELECT
                ... FOR UPDATE``) so a concurrent decision on the same
                application serialises behind this transaction.

        Returns:
            tuple[ApplicationEntity, JobEntity]: The application and its job.

        Raises:
            ValueError: If the application is missing, or the caller is not
                an owner of the application's job. Both cases raise the
                same generic message (mirroring
                ``ApplicationService._load_owned``) so response bodies don't
                leak which application ids exist to non-owners.
        """
        application = await self.application_repository.get_by_id(
            session, application_id, for_update=for_update
        )
        # Missing and not-owned must be indistinguishable: a distinct
        # "not an owner" message would let any authenticated caller probe
        # which application ids exist.
        if application is None:
            raise ValueError(f"application {application_id} not found")
        job = await self.job_repository.get_by_job_id(session, application.job_id)
        if job is None or current_user.user_id not in normalized_owner_ids(
            job.pipeline_config
        ):
            raise ValueError(f"application {application_id} not found")
        return application, job

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
                an owner of the application's job. Both cases raise the
                same generic message (mirroring
                ``ApplicationService._load_owned``) so response bodies don't
                leak which application ids exist to non-owners.
        """
        application, job = await self._load_owned_application(
            session, current_user, application_id
        )
        user = await self.users_repository.get_user_by_user_id(
            session, application.user_id
        )
        current_sub = await self.application_submission_repository.get_current(
            session, application_id
        )
        # The embedded ApplicationDto's `editable` is deliberately left at
        # its default (False) here: it encodes the CANDIDATE's edit window
        # (first stage / pending / unfrozen), which the owner-facing detail
        # UI doesn't consume yet. Recompute via
        # ApplicationService._is_editable if the board dialog ever needs it.
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

    async def _freeze_current_submission(
        self, session: AsyncSession, application_id: int
    ):
        """Mark an application's current submission version as frozen.

        Fetches the highest-version submission and sets ``is_frozen=True``.
        Safe to call on an already-frozen submission (idempotent re-write of
        the same value). ``change_stage`` calls this unconditionally on
        every stage change; ``set_sub_status`` only calls it the first time
        an application leaves ``"pending"``, so it isn't invoked (and no
        extra write happens) on later, already-frozen transitions.

        Args:
            session (AsyncSession): Active database async session.
            application_id (int): The owning application.

        Returns:
            ApplicationSubmissionEntity | None: The (now-frozen) current
                submission, or None if the application has none yet.
        """
        current_sub = await self.application_submission_repository.get_current(
            session, application_id
        )
        if current_sub is not None:
            current_sub.is_frozen = True
            current_sub = await self.application_submission_repository.update(
                session, current_sub
            )
        return current_sub

    async def change_stage(
        self,
        session: AsyncSession,
        current_user: UserContextDto,
        application_id: int,
        dto: StageChangeDto,
    ) -> ApplicationDto:
        """Advance or reject an application, per the job's configured pipeline.

        Row-locks the application for the duration of the transaction so two
        concurrent decisions on the same application serialise. On reject,
        records the reason/note/origin stage under ``tags["reject"]``. The
        target's sub_status resets to ``"pending"`` for pipeline stages, or
        ``None`` for terminal stages (HIRED/REJECTED). Every stage change
        freezes the application's current submission version, since once a
        decision has been made on it, the candidate must not be able to edit
        the record the decision was based on.

        Args:
            session (AsyncSession): Active database async session.
            current_user (UserContextDto): The authenticated caller.
            application_id (int): The application to move.
            dto (StageChangeDto): The target stage and, for rejects, the
                reason/note.

        Returns:
            ApplicationDto: The refreshed application.

        Raises:
            ValueError: If the application is missing, the caller is not an
                owner (collapsed to the same "not found" message as
                ``get_application_detail``), or the transition is not legal
                for the job's configured pipeline
                (``stage_machine.validate_transition``).
        """
        application, job = await self._load_owned_application(
            session, current_user, application_id, for_update=True
        )
        from_stage = application.stage
        stage_machine.validate_transition(job.pipeline_config, from_stage, dto.to_stage)

        if dto.to_stage == ApplicationStage.REJECTED:
            application.tags = {
                **(application.tags or {}),
                "reject": {
                    "reason": dto.reason,
                    "note": dto.note,
                    "fromStage": from_stage.value,
                    "at": datetime.now(timezone.utc).isoformat(),
                },
            }
        application.stage = dto.to_stage
        application.sub_status = (
            "pending"
            if dto.to_stage in stage_machine.configured_stages(job.pipeline_config)
            else None
        )

        current_sub = await self._freeze_current_submission(session, application_id)
        application = await self.application_repository.update(session, application)
        await session.commit()
        # `editable` encodes the CANDIDATE's edit window (see
        # get_application_detail's note); a fresh stage/sub_status decision
        # is never in that window, so this is always False here.
        return self.recruiting_mapper.to_application_dto(
            application, current_sub, editable=False
        )

    async def set_sub_status(
        self,
        session: AsyncSession,
        current_user: UserContextDto,
        application_id: int,
        dto: SubStatusChangeDto,
    ) -> ApplicationDto:
        """Manually switch an application's sub_status within its current stage.

        The first move away from ``"pending"`` freezes the application's
        current submission version (one-way: switching between later
        non-pending values doesn't re-freeze since it's already frozen, and
        moving back to ``"pending"`` never unfreezes it).

        Args:
            session (AsyncSession): Active database async session.
            current_user (UserContextDto): The authenticated caller.
            application_id (int): The application to update.
            dto (SubStatusChangeDto): The target sub_status.

        Returns:
            ApplicationDto: The refreshed application.

        Raises:
            ValueError: If the application is missing, the caller is not an
                owner (collapsed "not found" message), or ``dto.sub_status``
                isn't valid for the application's current stage
                (``stage_machine.validate_sub_status``).
        """
        application, _job = await self._load_owned_application(
            session, current_user, application_id, for_update=True
        )
        stage_machine.validate_sub_status(application.stage, dto.sub_status)

        current_value = application.sub_status or "pending"
        if current_value == "pending" and dto.sub_status != "pending":
            current_sub = await self._freeze_current_submission(session, application_id)
        else:
            current_sub = await self.application_submission_repository.get_current(
                session, application_id
            )
        application.sub_status = dto.sub_status

        application = await self.application_repository.update(session, application)
        await session.commit()
        return self.recruiting_mapper.to_application_dto(
            application, current_sub, editable=False
        )

    async def blacklist(
        self,
        session: AsyncSession,
        current_user: UserContextDto,
        dto: BlacklistDto,
    ) -> ApplicationDto:
        """Block a user org-wide and close out the triggering application.

        Deliberately NOT owner-gated: unlike every other write in this
        service, this does not check whether ``current_user`` owns the
        triggering application's job. It's an org-level sanction — whoever
        holds ``Permission.RECRUITING_BLACKLIST_WRITE`` (checked at the
        route) may blacklist any user off any application, regardless of
        which posting surfaced the abuse (2026-06-26 decision).

        Row-locks the application for the duration of the transaction, same
        as ``change_stage``/``set_sub_status``, and freezes its current
        submission version since the application is being closed out.

        Args:
            session (AsyncSession): Active database async session.
            current_user (UserContextDto): The authenticated caller,
                recorded as ``blocked_by``.
            dto (BlacklistDto): The target user/application and the
                (required, non-blank) reason.

        Returns:
            ApplicationDto: The now-REJECTED, blacklist-tagged application.

        Raises:
            ValueError: If the target user is missing, the application is
                missing, or the application does not belong to
                ``dto.user_id``.
        """
        user = await self.users_repository.get_user_by_user_id(session, dto.user_id)
        if user is None:
            raise ValueError(f"user {dto.user_id} not found")
        user.is_blocked = True
        user.blocked_by = current_user.user_id
        user.blocked_at = datetime.now(timezone.utc)
        user.blocked_reason = dto.reason

        application = await self.application_repository.get_by_id(
            session, dto.application_id, for_update=True
        )
        if application is None or application.user_id != dto.user_id:
            raise ValueError(f"application {dto.application_id} not found")

        application.stage = ApplicationStage.REJECTED
        application.tags = {**(application.tags or {}), "blacklisted": True}
        application.sub_status = None

        current_sub = await self._freeze_current_submission(
            session, dto.application_id
        )
        application = await self.application_repository.update(session, application)
        await session.commit()
        return self.recruiting_mapper.to_application_dto(
            application, current_sub, editable=False
        )
