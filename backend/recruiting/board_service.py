from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from backend.dto.application_dto import ApplicationDto
from backend.dto.board_dto import (
    ApplicationDetailDto,
    BlacklistDto,
    BoardCardDto,
    BoardJobDto,
    PipelineStageInfoDto,
    ReassignDto,
    RoundChangeDto,
    StageChangeDto,
    SubStatusChangeDto,
)
from backend.dto.user_context_dto import UserContextDto
from backend.common.permissions import Permission
from backend.common.recruiting_enums import ApplicationStage
from backend.entity.application_entity import ApplicationEntity
from backend.entity.job_entity import JobEntity
from backend.recruiting import stage_machine
from backend.recruiting.pipeline_owners import normalized_owner_ids

# Stages that carry an interview assignment/evaluation (sub-project #3
# slice 1); OFFER has no rubric and is not assignable.
INTERVIEW_STAGES = {
    ApplicationStage.RECRUITER_SCREENING,
    ApplicationStage.BEHAVIORAL,
    ApplicationStage.TECH,
    ApplicationStage.BOARD_REVIEW,
}


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
        resume_storage,
        application_assignment_repository,
        user_permissions_repository,
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
            resume_storage (ResumeStorage): Content-addressed résumé download,
                for the owner-facing proxy download route.
            application_assignment_repository (ApplicationAssignmentRepository):
                Per-(application, stage, round) interviewer assignment data access.
            user_permissions_repository (UserPermissionsRepository): Used to
                verify a proposed assignee actively holds
                ``Permission.RECRUITING_INTERVIEW_EVALUATE``.
        """
        self.job_repository = job_repository
        self.application_repository = application_repository
        self.application_submission_repository = application_submission_repository
        self.users_repository = users_repository
        self.recruiting_mapper = recruiting_mapper
        self.resume_storage = resume_storage
        self.application_assignment_repository = application_assignment_repository
        self.user_permissions_repository = user_permissions_repository

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
                configured pipeline stages (and each stage's configured
                round count) in global order.
        """
        jobs = await self.job_repository.list_all(session)
        return [
            BoardJobDto(
                id=job.job_id,
                title=job.title,
                kind=job.kind,
                stages=[
                    PipelineStageInfoDto(
                        stage=stage.value,
                        rounds=stage_machine.rounds_for_stage(
                            job.pipeline_config, stage
                        ),
                    )
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

        Each interview-stage card's ``reviewer_name`` resolves to: the
        explicit assignment for that card's ``(stage, current_round)`` if
        one exists; otherwise, only at round 1 and only for
        recruiter_screening/behavioral, the job's configured
        ``default_assignee_id`` for that stage; otherwise None. Non-interview
        stages always get ``reviewer_name=None``.

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
        job = await self._require_owner(session, current_user, job_id)
        rows = await self.application_repository.list_by_job(session, job_id)

        default_by_stage: dict[ApplicationStage, int] = {}
        for entry in (job.pipeline_config or {}).get("stages") or []:
            if not isinstance(entry, dict):
                continue
            default_id = entry.get("defaultAssigneeId")
            if default_id is None:
                continue
            try:
                stage = ApplicationStage(entry.get("stage"))
            except ValueError:
                continue
            default_by_stage[stage] = default_id

        application_ids = [application.application_id for application, _ in rows]
        assignments = (
            await self.application_assignment_repository.list_by_application_ids(
                session, application_ids
            )
        )
        assignment_by_key: dict[tuple[int, ApplicationStage, int], int] = {
            (a.application_id, a.stage, a.round): a.assignee_id for a in assignments
        }

        name_ids = {a.assignee_id for a in assignments} | set(default_by_stage.values())
        reviewers = await self.users_repository.get_all_by_ids(session, list(name_ids))
        names_by_id = {
            u.user_id: f"{u.first_name} {u.last_name}".strip() for u in reviewers
        }

        board: dict[str, list[BoardCardDto]] = {}
        for application, user in rows:
            reviewer_name = None
            if application.stage in INTERVIEW_STAGES:
                assignee_id = assignment_by_key.get((
                    application.application_id,
                    application.stage,
                    application.current_round,
                ))
                if assignee_id is None and application.current_round == 1:
                    assignee_id = default_by_stage.get(application.stage)
                if assignee_id is not None:
                    reviewer_name = names_by_id.get(assignee_id)
            card = self.recruiting_mapper.to_board_card_dto(
                application, user, reviewer_name=reviewer_name
            )
            board.setdefault(application.stage.value, []).append(card)
        return board

    async def _load_owned_application(
        self,
        session: AsyncSession,
        current_user: UserContextDto,
        application_id: int,
        *,
        for_update: bool = False,
        allow_assignee: bool = False,
    ) -> tuple[ApplicationEntity, JobEntity]:
        """Load an application and assert the caller may read/write it.

        Args:
            session (AsyncSession): Active database async session.
            current_user (UserContextDto): The authenticated caller.
            application_id (int): The application to load.
            for_update (bool): When True, row-locks the application (``SELECT
                ... FOR UPDATE``) so a concurrent decision on the same
                application serialises behind this transaction.
            allow_assignee (bool): When True, a caller who is the
                application's current-stage assignee (but not an owner)
                also passes — used by the read path (``get_application_detail``)
                now that owners and assignees share one detail page
                (sub-project #3 slice 1). Mutation paths (``change_stage``,
                ``set_sub_status``, ``reassign``, ``blacklist``) leave this
                False and stay owner-only.

        Returns:
            tuple[ApplicationEntity, JobEntity]: The application and its job.

        Raises:
            ValueError: If the application is missing, or the caller is
                neither an owner of the application's job nor (when
                ``allow_assignee`` is True) the application's current-stage
                assignee. All cases raise the same generic message
                (mirroring ``ApplicationService._load_owned``) so response
                bodies don't leak which application ids exist to
                unauthorized callers.
        """
        application = await self.application_repository.get_by_id(
            session, application_id, for_update=for_update
        )
        # Missing and not-owned/not-assignee must be indistinguishable: a
        # distinct message would let any authenticated caller probe which
        # application ids exist.
        if application is None:
            raise ValueError(f"application {application_id} not found")
        job = await self.job_repository.get_by_job_id(session, application.job_id)
        is_owner = job is not None and current_user.user_id in normalized_owner_ids(
            job.pipeline_config
        )
        is_assignee = False
        if not is_owner and allow_assignee:
            assignment = await self.application_assignment_repository.get(
                session, application_id, application.stage, application.current_round
            )
            is_assignee = (
                assignment is not None
                and assignment.assignee_id == current_user.user_id
            )
        if job is None or not (is_owner or is_assignee):
            raise ValueError(f"application {application_id} not found")
        return application, job

    async def get_application_detail(
        self,
        session: AsyncSession,
        current_user: UserContextDto,
        application_id: int,
    ) -> ApplicationDetailDto:
        """Return the full view of one application, for its owner or assignee.

        Readable by either a configured owner of the job, or (as of
        sub-project #3 slice 1) the application's current-stage assignee —
        PR 3 merges the owner's board dialog and the assignee's evaluation
        view into one shared page served by this same read endpoint.

        Args:
            session (AsyncSession): Active database async session.
            current_user (UserContextDto): The authenticated caller.
            application_id (int): The application to load.

        Returns:
            ApplicationDetailDto: The application, applicant identity,
                résumé availability, the job's live form schema (so the
                dialog can label answers by question id), and two role
                signals — ``is_owner`` and ``assignee_id`` — so the frontend
                can decide which of the owner-decision area / evaluator
                rubric area to render without a second round-trip.

        Raises:
            ValueError: If the application is missing, or the caller is
                neither an owner of the application's job nor its
                current-stage assignee. All cases raise the same generic
                message (mirroring ``ApplicationService._load_owned``) so
                response bodies don't leak which application ids exist to
                unauthorized callers.
        """
        application, job = await self._load_owned_application(
            session, current_user, application_id, allow_assignee=True
        )
        user = await self.users_repository.get_user_by_user_id(
            session, application.user_id
        )
        current_sub = await self.application_submission_repository.get_current(
            session, application_id
        )
        is_owner = current_user.user_id in normalized_owner_ids(job.pipeline_config)
        assignment = await self.application_assignment_repository.get(
            session, application_id, application.stage, application.current_round
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
            is_owner=is_owner,
            assignee_id=assignment.assignee_id if assignment is not None else None,
        )

    async def get_resume(
        self,
        session: AsyncSession,
        current_user: UserContextDto,
        application_id: int,
    ) -> bytes:
        """Return an application's résumé bytes, for the proxy download button
        on the shared application detail page (#138).

        Args:
            session (AsyncSession): Active database async session.
            current_user (UserContextDto): The authenticated caller.
            application_id (int): The application whose résumé to fetch.

        Returns:
            bytes: The raw PDF bytes, fetched from ``resume_storage``.

        Raises:
            ValueError: If the application is missing, the caller is neither
                an owner nor its current-stage assignee (collapsed "not
                found" message, same as ``get_application_detail``), or the
                application's current submission has no résumé on file.
        """
        _application, _job = await self._load_owned_application(
            session, current_user, application_id, allow_assignee=True
        )
        current_sub = await self.application_submission_repository.get_current(
            session, application_id
        )
        if current_sub is None or not current_sub.resume_object_key:
            raise ValueError(f"no resume on file for application {application_id}")
        return self.resume_storage.get(current_sub.resume_object_key)

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

    async def _validate_interview_assignee(
        self, session: AsyncSession, assignee_id: int
    ) -> None:
        """Assert an assignee is an active RECRUITING_INTERVIEW_EVALUATE holder.

        Args:
            session (AsyncSession): Active database async session.
            assignee_id (int): The proposed assignee's user id.

        Raises:
            ValueError: If ``assignee_id`` is not an active holder of
                ``Permission.RECRUITING_INTERVIEW_EVALUATE``.
        """
        pool = await self.user_permissions_repository.get_active_users_with_permission(
            session, Permission.RECRUITING_INTERVIEW_EVALUATE.value
        )
        if assignee_id not in {u.user_id for u in pool}:
            raise ValueError(
                f"assignee {assignee_id} is not an active interview evaluator"
            )

    async def change_stage(
        self,
        session: AsyncSession,
        current_user: UserContextDto,
        application_id: int,
        dto: StageChangeDto,
    ) -> ApplicationDto:
        """Advance or reject an application, per the job's configured pipeline.

        Row-locks the application for the duration of the transaction so two
        concurrent decisions on the same application serialise. When
        ``dto.to_stage`` is an interview stage (``INTERVIEW_STAGES``), an
        assignee must be supplied and must be an active holder of
        ``Permission.RECRUITING_INTERVIEW_EVALUATE``; the assignment is then
        persisted via ``application_assignment_repository.upsert``. Terminal
        targets (HIRED/REJECTED) ignore ``dto.assignee_id`` if present, since
        there's no interview to assign. On reject, records the
        reason/note/origin stage under ``tags["reject"]``. The target's
        sub_status resets to ``"pending"`` for pipeline stages, or ``None``
        for terminal stages. Every stage change freezes the application's
        current submission version, since once a decision has been made on
        it, the candidate must not be able to edit the record the decision
        was based on.

        Args:
            session (AsyncSession): Active database async session.
            current_user (UserContextDto): The authenticated caller,
                recorded as the assignment's ``assigned_by`` when advancing
                into an interview stage.
            application_id (int): The application to move.
            dto (StageChangeDto): The target stage and, for rejects, the
                reason/note; for interview-stage advances, the assignee.

        Returns:
            ApplicationDto: The refreshed application.

        Raises:
            ValueError: If the application is missing, the caller is not an
                owner (collapsed to the same "not found" message as
                ``get_application_detail``), the transition is not legal for
                the job's configured pipeline
                (``stage_machine.validate_transition``), or (for interview
                stages) ``dto.assignee_id`` is missing or is not an active
                holder of ``Permission.RECRUITING_INTERVIEW_EVALUATE``.
        """
        application, job = await self._load_owned_application(
            session, current_user, application_id, for_update=True
        )
        from_stage = application.stage
        stage_machine.validate_transition(job.pipeline_config, from_stage, dto.to_stage)

        if dto.to_stage in INTERVIEW_STAGES:
            if dto.assignee_id is None:
                raise ValueError(
                    f"assignee is required when advancing to {dto.to_stage!s}"
                )
            await self._validate_interview_assignee(session, dto.assignee_id)
            # The target stage always starts at round 1 (current_round is
            # reset below), so the assignment is written for round 1.
            await self.application_assignment_repository.upsert(
                session,
                application_id,
                dto.to_stage,
                1,
                dto.assignee_id,
                current_user.user_id,
            )

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
        application.current_round = 1

        current_sub = await self._freeze_current_submission(session, application_id)
        application = await self.application_repository.update(session, application)
        await session.commit()
        # `editable` encodes the CANDIDATE's edit window (see
        # get_application_detail's note); a fresh stage/sub_status decision
        # is never in that window, so this is always False here.
        return self.recruiting_mapper.to_application_dto(
            application, current_sub, editable=False
        )

    async def reassign(
        self,
        session: AsyncSession,
        current_user: UserContextDto,
        application_id: int,
        dto: ReassignDto,
    ) -> ApplicationDto:
        """Change the interviewer responsible for an application's current stage+round.

        Independent of Advance: usable any time the application sits in an
        interview stage, whether or not the outgoing assignee has submitted
        anything. Targets the application's current round (``current_round``)
        within its current stage — other rounds' assignments are untouched.
        Resets sub_status to "pending" so the new assignee starts from a
        clean slate; any evaluation the outgoing assignee already confirmed
        is untouched (it's a separate row keyed by its own evaluator_id —
        sub-project #3 slice 1's evaluation feature).

        Args:
            session (AsyncSession): Active database async session.
            current_user (UserContextDto): The authenticated caller.
            application_id (int): The application to reassign.
            dto (ReassignDto): The new assignee.

        Returns:
            ApplicationDto: The refreshed application.

        Raises:
            ValueError: If the application is missing, the caller is not an
                owner (collapsed "not found" message), the application's
                current stage is not an interview stage, or the assignee
                does not hold RECRUITING_INTERVIEW_EVALUATE.
        """
        application, _job = await self._load_owned_application(
            session, current_user, application_id, for_update=True
        )
        if application.stage not in INTERVIEW_STAGES:
            raise ValueError(
                f"application {application_id} is not in an interview stage"
            )
        await self._validate_interview_assignee(session, dto.assignee_id)
        await self.application_assignment_repository.upsert(
            session,
            application_id,
            application.stage,
            application.current_round,
            dto.assignee_id,
            current_user.user_id,
        )
        application.sub_status = "pending"
        application = await self.application_repository.update(session, application)
        await session.commit()
        current_sub = await self.application_submission_repository.get_current(
            session, application_id
        )
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

    async def set_round(
        self,
        session: AsyncSession,
        current_user: UserContextDto,
        application_id: int,
        dto: RoundChangeDto,
    ) -> ApplicationDto:
        """Manually advance an application to a round within its current stage.

        When the application's current stage is an interview stage
        (``INTERVIEW_STAGES``), an assignee must be supplied and must be an
        active holder of ``Permission.RECRUITING_INTERVIEW_EVALUATE``; the
        assignment is persisted for the target round via
        ``application_assignment_repository.upsert``. Non-interview stages
        (e.g. a multi-round ``offer``) ignore ``dto.assignee_id``. Resets
        ``sub_status`` to ``"pending"`` (mirrors ``reassign``/``change_stage``)
        so the new round doesn't inherit a prior round's ``"evaluated"`` state.

        Args:
            session (AsyncSession): Active database async session.
            current_user (UserContextDto): The authenticated caller,
                recorded as the assignment's ``assigned_by`` when the
                target stage is an interview stage.
            application_id (int): The application to update.
            dto (RoundChangeDto): The target round and, for interview
                stages, the assignee.

        Returns:
            ApplicationDto: The refreshed application.

        Raises:
            ValueError: If the application is missing, the caller is not an
                owner (collapsed "not found" message), ``dto.round`` is
                outside ``1..rounds_for_stage(...)`` for the application's
                current stage, or (for interview stages) ``dto.assignee_id``
                is missing or is not an active holder of
                ``Permission.RECRUITING_INTERVIEW_EVALUATE``.
        """
        application, job = await self._load_owned_application(
            session, current_user, application_id, for_update=True
        )
        max_round = stage_machine.rounds_for_stage(
            job.pipeline_config, application.stage
        )
        if not (1 <= dto.round <= max_round):
            raise ValueError(
                f"round {dto.round} is out of range for stage "
                f"{application.stage!s} (configured rounds: {max_round})"
            )
        if application.stage in INTERVIEW_STAGES:
            if dto.assignee_id is None:
                raise ValueError(
                    f"assignee is required when advancing to round {dto.round} "
                    f"of {application.stage!s}"
                )
            await self._validate_interview_assignee(session, dto.assignee_id)
            await self.application_assignment_repository.upsert(
                session,
                application_id,
                application.stage,
                dto.round,
                dto.assignee_id,
                current_user.user_id,
            )
        application.current_round = dto.round
        application.sub_status = "pending"

        current_sub = await self.application_submission_repository.get_current(
            session, application_id
        )
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
        application.current_round = 1

        current_sub = await self._freeze_current_submission(session, dto.application_id)
        application = await self.application_repository.update(session, application)
        await session.commit()
        return self.recruiting_mapper.to_application_dto(
            application, current_sub, editable=False
        )
