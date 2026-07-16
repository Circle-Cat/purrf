import re
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from backend.dto.application_dto import ApplicationDto
from backend.dto.board_dto import (
    ApplicationActivityDto,
    ApplicationAggregateDto,
    ApplicationDetailDto,
    BlacklistDto,
    BoardCardDto,
    BoardJobDto,
    CommentCreateDto,
    CommentDto,
    MentionedUserDto,
    OtherApplicationDto,
    PipelineStageInfoDto,
    ReassignDto,
    RoundChangeDto,
    StageChangeDto,
    SubStatusChangeDto,
)
from backend.dto.evaluation_dto import EvaluationDto
from backend.dto.user_context_dto import UserContextDto
from backend.common.permissions import Permission
from backend.common.recruiting_enums import ApplicationStage, NotificationType
from backend.entity.application_entity import ApplicationEntity
from backend.entity.job_entity import JobEntity
from backend.entity.notification_entity import NotificationEntity
from backend.recruiting import stage_machine
from backend.recruiting.pipeline_owners import normalized_owner_ids

_MENTION_TOKEN_RE = re.compile(r"@\[(\d+)\]")

# Stages that carry an interview assignment/evaluation (sub-project #3
# slice 1); OFFER has no rubric and is not assignable.
INTERVIEW_STAGES = {
    ApplicationStage.RECRUITER_SCREENING,
    ApplicationStage.BEHAVIORAL,
    ApplicationStage.TECH,
    ApplicationStage.BOARD_REVIEW,
}

# Per-event-type map of (raw assignee id field in `details`) -> (resolved
# name field to add). get_application_activity uses this to know which
# fields to look up and inject, without hardcoding each event type inline.
_ASSIGNEE_NAME_FIELDS: dict[str, tuple[tuple[str, str], ...]] = {
    "stage_changed": (("assigneeId", "assigneeName"),),
    "round_advanced": (("assigneeId", "assigneeName"),),
    "auto_assigned": (("assigneeId", "assigneeName"),),
    "reassigned": (
        ("fromAssigneeId", "fromAssigneeName"),
        ("toAssigneeId", "toAssigneeName"),
    ),
}

# Per-event-type map of (raw screen-rule id field in `details`) -> (resolved
# human-label field to add). get_application_activity uses this to surface
# WHICH configured screening rule produced an automated outcome, read-time
# only — the stored row keeps just the id.
_SCREEN_RULE_ID_FIELDS: dict[str, tuple[tuple[str, str], ...]] = {
    "auto_rejected": (("ruleId", "ruleLabel"),),
    "application_submitted": (
        ("screenQualifyRuleId", "screenQualifyRuleLabel"),
        ("screenAutoHireRuleId", "screenAutoHireRuleLabel"),
    ),
}


def _screen_rule_label(rule: dict) -> str:
    """A human-readable one-line label for a configured screening rule.

    Rules have no name field (frontend ids are just ``r1, r2, ...``), so the
    label is synthesized from the condition: e.g.
    ``"email domain not in google.com"`` or ``"answer to q_role equals
    mentor"``.

    Args:
        rule (dict): One entry of the job's ``screen_rules["rules"]``
            (camelCase keys, per ``ScreenRuleDto``'s serialization).

    Returns:
        str: The synthesized label.
    """
    condition = rule.get("condition") or {}
    operator = (condition.get("operator") or "").replace("_", " ")
    value = condition.get("value")
    values = ", ".join(value) if isinstance(value, list) else str(value or "")
    if condition.get("source") == "email_domain":
        subject = "email domain"
    elif condition.get("source") == "answer":
        subject = f"answer to {condition.get('questionId')}"
    else:
        subject = "condition"
    return f"{subject} {operator} {values}".strip()


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
        application_activity_repository,
        application_comment_repository,
        application_comment_mention_repository,
        evaluation_repository,
        notification_repository,
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
            application_activity_repository (ApplicationActivityRepository):
                Append-only audit log, written by ``change_stage``/
                ``reassign``/``set_round``/``set_sub_status``/``blacklist``
                and read by ``get_application_activity``.
            application_comment_repository (ApplicationCommentRepository):
                Append-only free-text discussion thread, written by
                ``add_comment`` and read by ``list_comments`` -- independent
                of ``application_activity_repository``.
            application_comment_mention_repository
                (ApplicationCommentMentionRepository): Append-only
                @-mention rows, written by ``add_comment`` and read by
                ``list_comments``/``list_mentionable_users``.
            evaluation_repository (EvaluationRepository): Used by
                ``get_other_applications`` to include a candidate's other
                applications' evaluations in the aggregation view.
            notification_repository (NotificationRepository): Written by
                ``change_stage``/``reassign`` (assignee notified) and
                ``add_comment`` (mentioned users notified) -- independent,
                explicit calls, not merged with the activity log (see the
                notification-system design spec for why).
        """
        self.job_repository = job_repository
        self.application_repository = application_repository
        self.application_submission_repository = application_submission_repository
        self.users_repository = users_repository
        self.recruiting_mapper = recruiting_mapper
        self.resume_storage = resume_storage
        self.application_assignment_repository = application_assignment_repository
        self.user_permissions_repository = user_permissions_repository
        self.application_activity_repository = application_activity_repository
        self.application_comment_repository = application_comment_repository
        self.application_comment_mention_repository = (
            application_comment_mention_repository
        )
        self.evaluation_repository = evaluation_repository
        self.notification_repository = notification_repository

    async def list_my_jobs(
        self, session: AsyncSession, current_user: UserContextDto
    ) -> list[BoardJobDto]:
        """List jobs the caller may open the board for, for the job switcher.

        Fetches every job via the same list-all repository call
        ``JobService.list_all_jobs`` uses, and filters in Python: a caller
        who holds ``Permission.RECRUITING_APPLICATION_READ_ALL`` gets every
        job; everyone else gets only the jobs they're a configured owner
        of. That's fine at dogfood scale (a handful of postings); an
        owner-indexed query would be worth adding if the job table grows.

        Args:
            session (AsyncSession): Active database async session.
            current_user (UserContextDto): The authenticated caller.

        Returns:
            list[BoardJobDto]: Jobs the caller may open the board for, each
                with its configured pipeline stages (and each stage's
                configured round count) in global order.
        """
        jobs = await self.job_repository.list_all(session)
        has_read_all = current_user.has_permission(
            Permission.RECRUITING_APPLICATION_READ_ALL
        )
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
            if has_read_all
            or current_user.user_id in normalized_owner_ids(job.pipeline_config)
        ]

    async def _require_owner(
        self,
        session: AsyncSession,
        current_user: UserContextDto,
        job_id: int,
        *,
        allow_read_all: bool = False,
    ) -> JobEntity:
        """Load a job and assert the caller is one of its configured owners.

        Args:
            session (AsyncSession): Active database async session.
            current_user (UserContextDto): The authenticated caller.
            job_id (int): The posting to load.
            allow_read_all (bool): When True, a caller who holds
                ``Permission.RECRUITING_APPLICATION_READ_ALL`` also passes,
                regardless of ownership.

        Returns:
            JobEntity: The loaded job.

        Raises:
            ValueError: If the job is missing, or the caller is neither an
                owner nor (when ``allow_read_all`` is True) a holder of
                ``RECRUITING_APPLICATION_READ_ALL``.
        """
        job = await self.job_repository.get_by_job_id(session, job_id)
        is_owner = job is not None and current_user.user_id in normalized_owner_ids(
            job.pipeline_config
        )
        is_read_all = allow_read_all and current_user.has_permission(
            Permission.RECRUITING_APPLICATION_READ_ALL
        )
        if job is None or not (is_owner or is_read_all):
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
        job = await self._require_owner(
            session, current_user, job_id, allow_read_all=True
        )
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
        allow_self: bool = False,
        allow_read_all: bool = False,
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
            allow_self (bool): When True, a caller who is the application's
                own submitter also passes, regardless of job ownership or
                assignment — used by ``get_resume`` so a candidate can read
                her own application's résumé bytes. Every other caller
                leaves this False and stays owner/assignee-only.
            allow_read_all (bool): When True, a caller who holds
                ``Permission.RECRUITING_APPLICATION_READ_ALL`` also passes,
                regardless of ownership/assignment. Read-only call sites opt
                in explicitly; every mutation path leaves this False, so
                ``read.all`` never grants a write.

        Returns:
            tuple[ApplicationEntity, JobEntity]: The application and its job.

        Raises:
            ValueError: If the application is missing, or the caller is
                none of: an owner of the application's job, (when
                ``allow_assignee`` is True) the application's current-stage
                assignee, (when ``allow_self`` is True) the application's
                own submitter, or (when ``allow_read_all`` is True) a holder
                of ``RECRUITING_APPLICATION_READ_ALL``. All cases raise the
                same generic message (mirroring
                ``ApplicationService._load_owned``) so response bodies
                don't leak which application ids exist to unauthorized
                callers.
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
        is_self = allow_self and application.user_id == current_user.user_id
        is_read_all = allow_read_all and current_user.has_permission(
            Permission.RECRUITING_APPLICATION_READ_ALL
        )
        if job is None or not (is_owner or is_assignee or is_self or is_read_all):
            raise ValueError(f"application {application_id} not found")
        return application, job

    async def get_application_detail(
        self,
        session: AsyncSession,
        current_user: UserContextDto,
        application_id: int,
    ) -> ApplicationDetailDto:
        """Return the full view of one application, for its owner, assignee, or read.all holder.

        Readable by any of: a configured owner of the job, the application's
        current-stage assignee (as of sub-project #3 slice 1, merging the
        owner's board dialog and the assignee's evaluation view into one
        shared page), or a caller holding ``Permission.RECRUITING_APPLICATION_READ_ALL``.

        Args:
            session (AsyncSession): Active database async session.
            current_user (UserContextDto): The authenticated caller.
            application_id (int): The application to load.

        Returns:
            ApplicationDetailDto: The application, applicant identity,
                résumé availability, the job's live form schema (so the
                dialog can label answers by question id), and three role
                signals — ``is_owner``, ``can_view``, and ``assignee_id`` —
                so the frontend can decide which of the owner-decision area /
                evaluator rubric area to render without a second round-trip.

        Raises:
            ValueError: If the application is missing, or the caller is
                none of: an owner of the application's job, its current-stage
                assignee, or a holder of ``Permission.RECRUITING_APPLICATION_READ_ALL``.
                All cases raise the same generic message (mirroring
                ``ApplicationService._load_owned``) so response bodies don't leak
                which application ids exist to unauthorized callers.
        """
        application, job = await self._load_owned_application(
            session,
            current_user,
            application_id,
            allow_assignee=True,
            allow_read_all=True,
        )
        user = await self.users_repository.get_user_by_user_id(
            session, application.user_id
        )
        current_sub = await self.application_submission_repository.get_current(
            session, application_id
        )
        is_owner = current_user.user_id in normalized_owner_ids(job.pipeline_config)
        can_view = is_owner or current_user.has_permission(
            Permission.RECRUITING_APPLICATION_READ_ALL
        )
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
            can_view=can_view,
            assignee_id=assignment.assignee_id if assignment is not None else None,
        )

    async def get_resume(
        self,
        session: AsyncSession,
        current_user: UserContextDto,
        application_id: int,
    ) -> bytes:
        """Return an application's résumé bytes, for the proxy download button
        on the shared application detail page (#138), including from the
        cross-posting aggregation view.

        Authorization checks every one of the candidate's applications, not
        just ``application_id`` itself: a caller who has no direct
        relationship to the requested application's job can still fetch its
        résumé if they're an owner/assignee/read.all holder on any OTHER
        application by the same candidate — the same "single entry gate"
        rule ``get_other_applications`` uses to decide what to show at all.
        Also preserves the existing ``allow_self`` path (#156): the
        candidate reading their own résumé still works, since ``application``
        is itself one of the rows ``candidate_rows`` iterates.

        Args:
            session (AsyncSession): Active database async session.
            current_user (UserContextDto): The authenticated caller.
            application_id (int): The application whose résumé to fetch.

        Returns:
            bytes: The raw PDF bytes, fetched from ``resume_storage``.

        Raises:
            ValueError: If the application is missing, the caller has no
                owner/assignee/self/read.all standing on it or any other
                application by the same candidate (collapsed "not found"
                message, same as ``get_application_detail``), or the
                application's current submission has no résumé on file.
        """
        application = await self.application_repository.get_by_id(
            session, application_id
        )
        if application is None:
            raise ValueError(f"application {application_id} not found")
        candidate_rows = await self.application_repository.list_by_user(
            session, application.user_id
        )
        authorized = False
        for candidate_application, _candidate_job in candidate_rows:
            try:
                await self._load_owned_application(
                    session,
                    current_user,
                    candidate_application.application_id,
                    allow_assignee=True,
                    allow_self=True,
                    allow_read_all=True,
                )
                authorized = True
                break
            except ValueError:
                continue
        if not authorized:
            raise ValueError(f"application {application_id} not found")
        current_sub = await self.application_submission_repository.get_current(
            session, application_id
        )
        if current_sub is None or not current_sub.resume_object_key:
            raise ValueError(f"no resume on file for application {application_id}")
        return self.resume_storage.get(current_sub.resume_object_key)

    async def get_application_activity(
        self,
        session: AsyncSession,
        current_user: UserContextDto,
        application_id: int,
    ) -> list[ApplicationActivityDto]:
        """Return an application's audit timeline, newest first, owner or read.all only.

        Unlike ``get_application_detail``/``get_resume``, this is NOT
        readable by the current-stage assignee — it's an owner-facing audit
        view (mirrors ``EvaluationSummary``'s owner-only placement on the
        frontend), not something an evaluator needs while grading. Accessible
        to the job's owners or callers holding ``Permission.RECRUITING_APPLICATION_READ_ALL``.

        Assignee names (for ``stage_changed``/``round_advanced``/
        ``auto_assigned``'s ``assigneeId``, and ``reassigned``'s
        ``fromAssigneeId``/``toAssigneeId``) are resolved the same way as
        ``actor_name`` — read-time only, via one combined batched lookup,
        never persisted back to the stored row. A raw id with no matching
        user resolves to ``f"User {id}"``, same fallback as ``actor_name``.

        Screening-rule ids (``auto_rejected``'s ``ruleId``, and
        ``application_submitted``'s ``screenQualifyRuleId``/
        ``screenAutoHireRuleId``) are likewise resolved read-time only,
        against the job's *current* ``screen_rules`` — never persisted back
        to the stored row. A rule id no longer present in the job's config
        (edited/removed since the row was written) resolves to
        ``f"rule {id} (no longer configured)"``.

        Args:
            session (AsyncSession): Active database async session.
            current_user (UserContextDto): The authenticated caller.
            application_id (int): The application to load history for.

        Returns:
            list[ApplicationActivityDto]: Newest first, each with the
                actor's resolved display name and, where applicable, its
                assignee name(s) and screen-rule label(s) merged into a
                copy of ``details`` (both resolved read-time only, never
                persisted back to the stored row).

        Raises:
            ValueError: If the application is missing, or the caller is neither
                an owner of the application's job nor a holder of
                ``Permission.RECRUITING_APPLICATION_READ_ALL`` (collapsed "not found"
                message, same as the other owner-facing reads).
        """
        _application, job = await self._load_owned_application(
            session, current_user, application_id, allow_read_all=True
        )
        rules_by_id = {
            rule.get("id"): rule
            for rule in ((job.screen_rules or {}).get("rules") or [])
            if isinstance(rule, dict)
        }
        rows = await self.application_activity_repository.list_by_application(
            session, application_id
        )
        ids_to_resolve = {row.actor_id for row in rows}
        for row in rows:
            for raw_field, _ in _ASSIGNEE_NAME_FIELDS.get(row.event_type, ()):
                raw_id = row.details.get(raw_field)
                if raw_id is not None:
                    ids_to_resolve.add(raw_id)
        users = await self.users_repository.get_all_by_ids(
            session, list(ids_to_resolve)
        )
        names_by_id = {
            user.user_id: f"{user.first_name} {user.last_name}".strip()
            for user in users
        }
        result = []
        for row in rows:
            details = {**row.details}
            for raw_field, name_field in _ASSIGNEE_NAME_FIELDS.get(row.event_type, ()):
                raw_id = details.get(raw_field)
                if raw_id is not None:
                    details[name_field] = names_by_id.get(raw_id, f"User {raw_id}")
            for id_field, label_field in _SCREEN_RULE_ID_FIELDS.get(row.event_type, ()):
                rule_id = details.get(id_field)
                if rule_id is None:
                    continue
                rule = rules_by_id.get(rule_id)
                details[label_field] = (
                    _screen_rule_label(rule)
                    if rule is not None
                    else f"rule {rule_id} (no longer configured)"
                )
            result.append(
                ApplicationActivityDto(
                    id=row.activity_id,
                    event_type=row.event_type,
                    details=details,
                    actor_id=row.actor_id,
                    actor_name=names_by_id.get(row.actor_id, f"User {row.actor_id}"),
                    created_at=row.created_at,
                )
            )
        return result

    async def get_other_applications(
        self,
        session: AsyncSession,
        current_user: UserContextDto,
        application_id: int,
    ) -> ApplicationAggregateDto:
        """Return a candidate's other applications, split into cross-job and
        same-job history, for the aggregation view on the shared
        application detail page.

        Reaching ``application_id``'s own detail page already required
        passing the same check this reuses
        (``_load_owned_application(allow_assignee=True, allow_read_all=True)``);
        once that passes, every OTHER application belonging to the same
        candidate is returned in full — submission snapshot and every
        evaluation row — regardless of the caller's relationship to those
        other jobs specifically. There is deliberately no second,
        per-other-application visibility check. Applications to other jobs
        go in ``other_jobs``; prior attempts on the SAME job (the detail
        page's own history) go in ``previous_same_job``, newest first. The
        currently-viewed application itself appears in neither list.

        Args:
            session (AsyncSession): Active database async session.
            current_user (UserContextDto): The authenticated caller.
            application_id (int): The application the caller is currently
                viewing; identifies the candidate whose other applications
                to list.

        Returns:
            ApplicationAggregateDto: ``other_jobs`` (cross-job applications)
                and ``previous_same_job`` (same-job prior attempts, newest
                first), each entry carrying its job title, full application
                snapshot, résumé availability, and every evaluation row
                submitted for it.

        Raises:
            ValueError: If ``application_id`` is missing, or the caller is
                neither an owner of its job, its current-stage assignee,
                nor a holder of ``RECRUITING_APPLICATION_READ_ALL``.
        """
        application, _job = await self._load_owned_application(
            session,
            current_user,
            application_id,
            allow_assignee=True,
            allow_read_all=True,
        )
        rows = await self.application_repository.list_by_user(
            session, application.user_id
        )

        async def _entry(other_application, other_job) -> OtherApplicationDto:
            current_sub = await self.application_submission_repository.get_current(
                session, other_application.application_id
            )
            evaluation_rows = await self.evaluation_repository.list_by_application(
                session, other_application.application_id
            )
            return OtherApplicationDto(
                application=self.recruiting_mapper.to_application_dto(
                    other_application, current_sub
                ),
                job_title=other_job.title,
                resume_available=bool(
                    current_sub is not None and current_sub.resume_object_key
                ),
                evaluations=[
                    EvaluationDto(
                        id=row.evaluation_id,
                        application_id=row.application_id,
                        stage=row.stage,
                        round=row.round,
                        evaluator_id=row.evaluator_id,
                        responses=row.responses,
                        is_confirmed=row.is_confirmed,
                        confirmed_at=row.confirmed_at,
                    )
                    for row in evaluation_rows
                ],
            )

        other_jobs: list[OtherApplicationDto] = []
        previous_same_job: list[OtherApplicationDto] = []
        for other_application, other_job in rows:
            if other_application.application_id == application_id:
                continue
            if other_application.job_id == application.job_id:
                previous_same_job.append(await _entry(other_application, other_job))
            else:
                other_jobs.append(await _entry(other_application, other_job))
        previous_same_job.sort(key=lambda o: o.application.id, reverse=True)
        return ApplicationAggregateDto(
            other_jobs=other_jobs, previous_same_job=previous_same_job
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
        ``dto.to_stage`` is an interview stage (``INTERVIEW_STAGES``),
        ``dto.assignee_id`` is optional: if supplied it must be an active
        holder of ``Permission.RECRUITING_INTERVIEW_EVALUATE`` and the
        assignment is persisted via ``application_assignment_repository.upsert``;
        if omitted, the target stage is simply left unassigned until the
        owner picks someone via ``reassign``. Terminal targets
        (HIRED/REJECTED) ignore ``dto.assignee_id`` if present, since there's
        no interview to assign. On reject, records the reason/note/origin
        stage under ``tags["reject"]``. The target's sub_status resets to
        ``"pending"`` for pipeline stages, or ``None`` for terminal stages.
        Every stage change freezes the application's current submission
        version, since once a decision has been made on it, the candidate
        must not be able to edit the record the decision was based on.

        Args:
            session (AsyncSession): Active database async session.
            current_user (UserContextDto): The authenticated caller,
                recorded as the assignment's ``assigned_by`` when advancing
                into an interview stage with an assignee.
            application_id (int): The application to move.
            dto (StageChangeDto): The target stage and, for rejects, the
                reason/note; for interview-stage advances, the optional
                assignee.

        Returns:
            ApplicationDto: The refreshed application.

        Raises:
            ValueError: If the application is missing, the caller is not an
                owner (collapsed to the same "not found" message as
                ``get_application_detail``), the transition is not legal for
                the job's configured pipeline
                (``stage_machine.validate_transition``), or (for interview
                stages) a supplied ``dto.assignee_id`` is not an active
                holder of ``Permission.RECRUITING_INTERVIEW_EVALUATE``.
        """
        application, job = await self._load_owned_application(
            session, current_user, application_id, for_update=True
        )
        from_stage = application.stage
        stage_machine.validate_transition(
            job.pipeline_config, from_stage, dto.to_stage, job.kind
        )

        new_interview_assignee = None
        if dto.to_stage in INTERVIEW_STAGES and dto.assignee_id is not None:
            await self._validate_interview_assignee(session, dto.assignee_id)
            # The target stage always starts at round 1 (current_round is
            # reset below), so the assignment is written for round 1.
            existing_assignment = await self.application_assignment_repository.get(
                session, application_id, dto.to_stage, 1
            )
            await self.application_assignment_repository.upsert(
                session,
                application_id,
                dto.to_stage,
                1,
                dto.assignee_id,
                current_user.user_id,
            )
            if (
                existing_assignment is None
                or existing_assignment.assignee_id != dto.assignee_id
            ):
                new_interview_assignee = dto.assignee_id

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
        await self.application_activity_repository.create(
            session,
            application_id,
            current_user.user_id,
            "stage_changed",
            details={
                "fromStage": from_stage.value,
                "toStage": dto.to_stage.value,
                **(
                    {"assigneeId": dto.assignee_id}
                    if dto.assignee_id is not None
                    else {}
                ),
                **(
                    {"reason": dto.reason, "note": dto.note}
                    if dto.to_stage == ApplicationStage.REJECTED
                    else {}
                ),
            },
        )
        if (
            new_interview_assignee is not None
            and new_interview_assignee != current_user.user_id
        ):
            await self.notification_repository.create(
                session,
                NotificationEntity(
                    user_id=new_interview_assignee,
                    type=NotificationType.ASSIGNED_TO_EVALUATE,
                    application_id=application_id,
                    round=1,
                    actor_user_id=current_user.user_id,
                ),
            )
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

        Does NOT reset sub_status to "pending" (a reassignment always means
        someone now owns it, so it should never read as untouched). Instead
        it promotes sub_status forward, in a way that reflects the new
        assignee's actual starting point rather than clearing progress:
        - recruiter_screening/board_review (sub-status set has
          "in_progress"): "pending"/unset -> "in_progress"; "evaluated" ->
          "in_progress" too, since one evaluation isn't enough and the new
          assignee still has to submit their own.
        - behavioral/tech (sub-status set uses scheduling/scheduled
          instead): "pending"/unset -> "scheduling" (the new assignee has
          to book a slot from scratch); "evaluated" -> "scheduled" (the
          interview itself already happened, only the evaluation needs
          redoing, so scheduling isn't required again).
        Any other current sub_status ("in_progress", "scheduling",
        "scheduled") is left exactly as it was — it already reflects an
        in-flight state that reassignment doesn't change. Any evaluation
        the outgoing assignee already confirmed is untouched (it's a
        separate row keyed by its own evaluator_id — sub-project #3 slice
        1's evaluation feature).

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
        previous_assignment = await self.application_assignment_repository.get(
            session, application_id, application.stage, application.current_round
        )
        await self.application_assignment_repository.upsert(
            session,
            application_id,
            application.stage,
            application.current_round,
            dto.assignee_id,
            current_user.user_id,
        )
        sub_statuses = stage_machine.SUB_STATUS_SETS.get(application.stage, ())
        if "in_progress" in sub_statuses:
            if application.sub_status in (None, "pending", "evaluated"):
                application.sub_status = "in_progress"
        elif "scheduling" in sub_statuses:
            if application.sub_status in (None, "pending"):
                application.sub_status = "scheduling"
            elif application.sub_status == "evaluated":
                application.sub_status = "scheduled"
        application = await self.application_repository.update(session, application)
        previous_assignee_id = (
            previous_assignment.assignee_id if previous_assignment is not None else None
        )
        await self.application_activity_repository.create(
            session,
            application_id,
            current_user.user_id,
            "reassigned",
            details={
                "stage": application.stage.value,
                "round": application.current_round,
                "fromAssigneeId": previous_assignee_id,
                "toAssigneeId": dto.assignee_id,
            },
        )
        if (
            dto.assignee_id != previous_assignee_id
            and dto.assignee_id != current_user.user_id
        ):
            await self.notification_repository.create(
                session,
                NotificationEntity(
                    user_id=dto.assignee_id,
                    type=NotificationType.ASSIGNED_TO_EVALUATE,
                    application_id=application_id,
                    round=application.current_round,
                    actor_user_id=current_user.user_id,
                ),
            )
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
        moving back to ``"pending"`` never unfreezes it). Logs a
        ``"sub_status_changed"`` activity entry.

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
        await self.application_activity_repository.create(
            session,
            application_id,
            current_user.user_id,
            "sub_status_changed",
            details={
                "stage": application.stage.value,
                "fromSubStatus": current_value,
                "toSubStatus": dto.sub_status,
            },
        )
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
        (``INTERVIEW_STAGES``) and ``dto.assignee_id`` is supplied, it must
        be an active holder of ``Permission.RECRUITING_INTERVIEW_EVALUATE``;
        the assignment is persisted for the target round via
        ``application_assignment_repository.upsert``. Supplying no assignee
        is allowed — mirrors ``change_stage``'s optional-assignee advance —
        and simply leaves the target round unassigned, to be picked up later
        via ``reassign``. Non-interview stages ignore ``dto.assignee_id``
        either way (though every currently-configurable stage is an interview
        stage — Offer, the one non-interview stage, is a fixed single-round
        step and cannot be configured with multiple rounds at all). Resets
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
                current stage, or a supplied ``dto.assignee_id`` is not an
                active holder of ``Permission.RECRUITING_INTERVIEW_EVALUATE``.
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
        if application.stage in INTERVIEW_STAGES and dto.assignee_id is not None:
            await self._validate_interview_assignee(session, dto.assignee_id)
            await self.application_assignment_repository.upsert(
                session,
                application_id,
                application.stage,
                dto.round,
                dto.assignee_id,
                current_user.user_id,
            )
        from_round = application.current_round
        application.current_round = dto.round
        application.sub_status = "pending"

        current_sub = await self.application_submission_repository.get_current(
            session, application_id
        )
        application = await self.application_repository.update(session, application)
        await self.application_activity_repository.create(
            session,
            application_id,
            current_user.user_id,
            "round_advanced",
            details={
                "stage": application.stage.value,
                "fromRound": from_round,
                "toRound": dto.round,
                **(
                    {"assigneeId": dto.assignee_id}
                    if dto.assignee_id is not None
                    else {}
                ),
            },
        )
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
        """Block a user org-wide and close out the triggering application
        and every other in-flight application of the user.

        Deliberately NOT owner-gated: unlike every other write in this
        service, this does not check whether ``current_user`` owns the
        triggering application's job. It's an org-level sanction — whoever
        holds ``Permission.RECRUITING_BLACKLIST_WRITE`` (checked at the
        route) may blacklist any user off any application, regardless of
        which posting surfaced the abuse (2026-06-26 decision).

        Row-locks the application for the duration of the transaction, same
        as ``change_stage``/``set_sub_status``, and freezes its current
        submission version since the application is being closed out. Logs
        a ``"blacklisted"`` activity entry (not ``"stage_changed"`` — this
        doesn't go through ``change_stage`` and carries its own reason).

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

        from_stage = application.stage
        application.stage = ApplicationStage.REJECTED
        application.tags = {**(application.tags or {}), "blacklisted": True}
        application.sub_status = None
        application.current_round = 1

        current_sub = await self._freeze_current_submission(session, dto.application_id)
        application = await self.application_repository.update(session, application)
        await self.application_activity_repository.create(
            session,
            dto.application_id,
            current_user.user_id,
            "blacklisted",
            details={"fromStage": from_stage.value, "reason": dto.reason},
        )

        # Close out every OTHER in-flight application of the same user: the
        # org-wide flag already auto-rejects future submissions, and leaving
        # live applications on other boards after a sanction was the gap
        # (2026-07-15 decision). Completed outcomes (HIRED) and already-
        # rejected rows are left untouched. Each row is re-fetched FOR UPDATE
        # so a concurrent stage decision on it can't interleave.
        rows = await self.application_repository.list_by_user(session, dto.user_id)
        for other, _job in rows:
            if other.application_id == dto.application_id:
                continue
            locked = await self.application_repository.get_by_id(
                session, other.application_id, for_update=True
            )
            if locked is None or locked.stage in (
                ApplicationStage.REJECTED,
                ApplicationStage.HIRED,
            ):
                continue
            other_from_stage = locked.stage
            locked.stage = ApplicationStage.REJECTED
            locked.tags = {**(locked.tags or {}), "blacklisted": True}
            locked.sub_status = None
            locked.current_round = 1
            await self._freeze_current_submission(session, locked.application_id)
            await self.application_repository.update(session, locked)
            await self.application_activity_repository.create(
                session,
                locked.application_id,
                current_user.user_id,
                "blacklisted",
                details={"fromStage": other_from_stage.value, "reason": dto.reason},
            )

        await session.commit()
        return self.recruiting_mapper.to_application_dto(
            application, current_sub, editable=False
        )

    async def _mentionable_user_ids(
        self, session: AsyncSession, application: ApplicationEntity, job: JobEntity
    ) -> set[int]:
        """Owner(s) plus the current-stage assignee, if any.

        The exact same population _load_owned_application's allow_assignee
        gate already authorizes to see this application's comments -- used
        both to answer "who can I @mention" and to validate mention tokens
        on submit.

        Args:
            session (AsyncSession): Active database async session.
            application (ApplicationEntity): The application being
                commented on.
            job (JobEntity): The application's job (for owner ids).

        Returns:
            set[int]: Mentionable user ids.
        """
        ids = set(normalized_owner_ids(job.pipeline_config))
        assignment = await self.application_assignment_repository.get(
            session,
            application.application_id,
            application.stage,
            application.current_round,
        )
        if assignment is not None:
            ids.add(assignment.assignee_id)
        return ids

    def _resolve_mentions(
        self, body: str, mentionable_ids: set[int]
    ) -> tuple[str, list[int]]:
        """Validate every @[id] token in a comment body.

        Args:
            body (str): The raw submitted comment text.
            mentionable_ids (set[int]): User ids currently allowed to be
                mentioned on this application.

        Returns:
            tuple[str, list[int]]: The body with any unauthorized token
                removed entirely (no display name exists to fall back to),
                and the de-duplicated, order-preserved list of validated
                mentioned ids.
        """
        validated_ids = []
        seen = set()
        for match in _MENTION_TOKEN_RE.finditer(body):
            uid = int(match.group(1))
            if uid in mentionable_ids and uid not in seen:
                validated_ids.append(uid)
                seen.add(uid)

        def _strip_invalid(match: re.Match) -> str:
            return match.group(0) if int(match.group(1)) in mentionable_ids else ""

        cleaned_body = _MENTION_TOKEN_RE.sub(_strip_invalid, body)
        return cleaned_body, validated_ids

    async def _resolve_mentioned_users(
        self, session: AsyncSession, mentioned_ids: list[int]
    ) -> list[MentionedUserDto]:
        """Resolve mentioned user ids to their current display names.

        Args:
            session (AsyncSession): Active database async session.
            mentioned_ids (list[int]): Validated mentioned user ids, in the
                order they should appear.

        Returns:
            list[MentionedUserDto]: One entry per id, name resolved fresh
                (never stored), falling back to "User {id}" if the user
                record is unexpectedly missing.
        """
        if not mentioned_ids:
            return []
        users = await self.users_repository.get_all_by_ids(session, mentioned_ids)
        names_by_id = {
            user.user_id: f"{user.first_name} {user.last_name}".strip()
            for user in users
        }
        return [
            MentionedUserDto(user_id=uid, name=names_by_id.get(uid, f"User {uid}"))
            for uid in mentioned_ids
        ]

    async def list_comments(
        self,
        session: AsyncSession,
        current_user: UserContextDto,
        application_id: int,
    ) -> list[CommentDto]:
        """Return every comment on an application, newest first.

        Readable by either a configured owner of the job, the application's
        current-stage assignee, or a holder of
        ``Permission.RECRUITING_APPLICATION_READ_ALL`` -- same access as
        ``get_application_detail``. Independent of
        ``get_application_activity``: comments are free-text discussion,
        not the structured audit log, and (unlike the activity timeline)
        are readable by the current-stage assignee too.

        Args:
            session (AsyncSession): Active database async session.
            current_user (UserContextDto): The authenticated caller.
            application_id (int): The application to list comments for.

        Returns:
            list[CommentDto]: Newest first, each with the author's resolved
                display name and any @-mentions resolved to current names.

        Raises:
            ValueError: If the application is missing, or the caller is
                none of: an owner of the application's job, its
                current-stage assignee, or a ``read.all`` holder. All cases
                raise the same generic message so response bodies don't
                leak which application ids exist to unauthorized callers.
        """
        await self._load_owned_application(
            session,
            current_user,
            application_id,
            allow_assignee=True,
            allow_read_all=True,
        )
        rows = await self.application_comment_repository.list_by_application(
            session, application_id
        )
        authors = await self.users_repository.get_all_by_ids(
            session, list({row.author_id for row in rows})
        )
        names_by_id = {
            user.user_id: f"{user.first_name} {user.last_name}".strip()
            for user in authors
        }
        comment_ids = [row.comment_id for row in rows]
        mention_rows = (
            await self.application_comment_mention_repository.get_by_comment_ids(
                session, comment_ids
            )
        )
        mentioned_users = await self.users_repository.get_all_by_ids(
            session, list({m.mentioned_user_id for m in mention_rows})
        )
        mention_names_by_id = {
            user.user_id: f"{user.first_name} {user.last_name}".strip()
            for user in mentioned_users
        }
        mentions_by_comment: dict[int, list[MentionedUserDto]] = {}
        for m in mention_rows:
            mentions_by_comment.setdefault(m.comment_id, []).append(
                MentionedUserDto(
                    user_id=m.mentioned_user_id,
                    name=mention_names_by_id.get(
                        m.mentioned_user_id, f"User {m.mentioned_user_id}"
                    ),
                )
            )
        return [
            CommentDto(
                id=row.comment_id,
                application_id=row.application_id,
                author_id=row.author_id,
                author_name=names_by_id.get(row.author_id, f"User {row.author_id}"),
                body=row.body,
                created_at=row.created_at,
                mentions=mentions_by_comment.get(row.comment_id, []),
            )
            for row in rows
        ]

    async def add_comment(
        self,
        session: AsyncSession,
        current_user: UserContextDto,
        application_id: int,
        dto: CommentCreateDto,
    ) -> CommentDto:
        """Post a comment on an application.

        Same access as ``list_comments``: owner, current-stage assignee, or
        a ``read.all`` holder -- the one write action bundled into that
        otherwise read-only override. Any ``@[userId]`` tokens in the body
        are validated against the application's mentionable set (see
        ``_mentionable_user_ids``), which is deliberately narrower than
        this posting-access check: only the owner(s)/current-stage
        assignee are mentionable, not every ``read.all`` holder org-wide --
        an unauthorized token (including one naming a real but
        non-mentionable ``read.all`` user) is stripped from the stored
        body and creates no mention row. The frontend picker only ever
        offers valid targets, but the server never trusts that.

        Args:
            session (AsyncSession): Active database async session.
            current_user (UserContextDto): The authenticated caller,
                recorded as the comment's author.
            application_id (int): The application to comment on.
            dto (CommentCreateDto): The comment text.

        Returns:
            CommentDto: The newly created comment, with any validated
                mentions resolved to current display names.

        Raises:
            ValueError: If the application is missing, the caller is none
                of: an owner of the application's job, its current-stage
                assignee, or a ``read.all`` holder (collapsed "not found"
                message), or the body is blank after stripping any
                unauthorized mention tokens -- e.g. a submission
                consisting entirely of one invalid ``@[id]`` token passes
                ``CommentCreateDto``'s raw-body validator (it's non-empty
                text) but must still be rejected once the invalid mention
                is stripped out, with the exact same message that
                validator raises for a blank raw submission.
        """
        application, job = await self._load_owned_application(
            session,
            current_user,
            application_id,
            allow_assignee=True,
            allow_read_all=True,
        )
        mentionable_ids = await self._mentionable_user_ids(session, application, job)
        body, mentioned_ids = self._resolve_mentions(dto.body, mentionable_ids)
        if not body.strip():
            raise ValueError("comment text is required")
        row = await self.application_comment_repository.create(
            session, application_id, current_user.user_id, body
        )
        if mentioned_ids:
            await self.application_comment_mention_repository.create_mentions(
                session, row.comment_id, mentioned_ids
            )
            for mentioned_id in mentioned_ids:
                if mentioned_id == current_user.user_id:
                    continue
                await self.notification_repository.create(
                    session,
                    NotificationEntity(
                        user_id=mentioned_id,
                        type=NotificationType.MENTIONED,
                        application_id=application_id,
                        comment_id=row.comment_id,
                        actor_user_id=current_user.user_id,
                    ),
                )
        await session.commit()
        author = await self.users_repository.get_user_by_user_id(
            session, current_user.user_id
        )
        author_name = (
            f"{author.first_name} {author.last_name}".strip()
            if author is not None
            else f"User {current_user.user_id}"
        )
        mentions = await self._resolve_mentioned_users(session, mentioned_ids)
        return CommentDto(
            id=row.comment_id,
            application_id=row.application_id,
            author_id=row.author_id,
            author_name=author_name,
            body=row.body,
            created_at=row.created_at,
            mentions=mentions,
        )

    async def list_mentionable_users(
        self,
        session: AsyncSession,
        current_user: UserContextDto,
        application_id: int,
    ) -> list[MentionedUserDto]:
        """Everyone who can currently be @-mentioned on this application.

        Callable by anyone who can see the comment thread -- owner,
        current-stage assignee, or a ``read.all`` holder, same as
        ``list_comments`` -- but the returned candidate set itself is
        narrower: job owner(s) plus the current-stage assignee only (see
        ``_mentionable_user_ids``). A ``read.all`` holder can view and post
        comments but is deliberately not itself mentionable -- that set is
        for who has direct operational responsibility on this specific
        application, not everyone with org-wide oversight.

        Args:
            session (AsyncSession): Active database async session.
            current_user (UserContextDto): The authenticated caller.
            application_id (int): The application to list mentionable users
                for.

        Returns:
            list[MentionedUserDto]: One entry per mentionable user, sorted
                by display name (set iteration order is not stable, and a
                name-sorted list makes for a sane, deterministic picker).

        Raises:
            ValueError: If the application is missing, or the caller is
                none of: an owner, the current-stage assignee, or a
                ``read.all`` holder (collapsed "not found" message, same
                as ``list_comments``).
        """
        application, job = await self._load_owned_application(
            session,
            current_user,
            application_id,
            allow_assignee=True,
            allow_read_all=True,
        )
        mentionable_ids = await self._mentionable_user_ids(session, application, job)
        users = await self.users_repository.get_all_by_ids(
            session, list(mentionable_ids)
        )
        return sorted(
            (
                MentionedUserDto(
                    user_id=user.user_id,
                    name=f"{user.first_name} {user.last_name}".strip(),
                )
                for user in users
            ),
            key=lambda dto: dto.name,
        )
