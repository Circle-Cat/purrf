from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.recruiting_enums import (
    ApplicationLockReason,
    ApplicationStage,
    PUBLICLY_VISIBLE_JOB_STATUSES,
    RecruitingEvent,
)
from backend.dto.application_dto import (
    ApplicationDto,
    ApplicationEditDto,
    ApplicationSubmitDto,
)
from backend.dto.job_config_dto import (
    LONG_TEXT_MAX_LENGTH,
    SHORT_TEXT_MAX_LENGTH,
)
from backend.dto.user_context_dto import UserContextDto
from backend.entity.application_entity import ApplicationEntity
from backend.entity.application_submission_entity import ApplicationSubmissionEntity
from backend.notification_management.event_recorder import record_event
from backend.recruiting import cooldown, form_visibility, screen_rules, stage_machine
from backend.recruiting.board_service import INTERVIEW_STAGES
from backend.recruiting.pipeline_owners import normalized_owner_ids


# The fields every candidate must give, whatever the posting asks for: the
# form marks them with a plain asterisk rather than a configurable one.
_REQUIRED_PERSONAL = (
    ("firstName", "a first name"),
    ("lastName", "a last name"),
    ("timezone", "a timezone"),
)

# What makes one row of each list an entry rather than a blank the candidate
# started and left. Field names are the form's, because the form's shape is
# what goes on the wire and gets stored verbatim.
_EDUCATION_FIELDS = (
    ("institution", "school"),
    ("degree", "degree"),
    ("field", "field of study"),
)
_EXPERIENCE_FIELDS = (("title", "title"), ("company", "company"))

# Which `profile_config` key gates each list.
_SECTION_CONFIG_KEY = {"education": "education", "experience": "workExperience"}


class ApplicationService:
    """Candidate-facing application submission + auto-screening."""

    def __init__(
        self,
        application_repository,
        application_submission_repository,
        job_repository,
        users_repository,
        recruiting_mapper,
        application_assignment_repository,
        notification_repository,
        user_emails_repository,
        onboarding_training_service,
    ):
        """
        Args:
            application_repository (ApplicationRepository): Container data access.
            application_submission_repository (ApplicationSubmissionRepository):
                Versioned-submission data access.
            job_repository (JobRepository): Posting data access.
            users_repository (UsersRepository): Reads is_blocked.
            user_emails_repository (UserEmailsRepository): The applicant's
                confirmed email claims for screen-rule email matching.
            recruiting_mapper (RecruitingMapper): Entity→DTO conversion.
            application_assignment_repository (ApplicationAssignmentRepository):
                Used to materialize a stage's configured default assignee
                into a real assignment row when an application first lands
                there (see ``_assign_default_if_configured``).
            notification_repository (NotificationRepository): Same -- notification
                rows are written by ``record_event`` from the resolved
                recipients, not by this service.
            onboarding_training_service (OnboardingTrainingService): Assigns
                the mentorship onboarding training task when an `auto_hire`
                screen rule lands the submission directly on HIRED.
        """
        self.application_repository = application_repository
        self.application_submission_repository = application_submission_repository
        self.job_repository = job_repository
        self.users_repository = users_repository
        self.recruiting_mapper = recruiting_mapper
        self.application_assignment_repository = application_assignment_repository
        self.notification_repository = notification_repository
        self.user_emails_repository = user_emails_repository
        self.onboarding_training_service = onboarding_training_service

    @staticmethod
    def _today():
        """Current UTC date (seam for tests)."""
        return datetime.now(timezone.utc).date()

    @staticmethod
    def _snapshot(dto, job) -> dict:
        """Build the immutable submission snapshot from a submit/edit DTO.

        Stores the job's form schema next to the answers so the answers can
        always be labeled with the questions the candidate actually saw:
        ``job.form_schema`` is overwritten in place whenever an owner edits
        the posting, and no historical copy is kept anywhere else.

        Args:
            dto (ApplicationSubmitDto | ApplicationEditDto): The payload.
            job (JobEntity): The posting being applied to, read for its
                live ``form_schema`` at the moment of this write.

        Returns:
            dict: The snapshot persisted as ``ApplicationSubmissionEntity.submission``.
        """
        return {
            "personal": dto.personal,
            "education": dto.education,
            "experience": dto.experience,
            "answers": dto.answers,
            "formSchema": job.form_schema or {"questions": []},
        }

    @staticmethod
    def _answered(value) -> bool:
        """True when an answer is a non-empty scalar or non-empty list."""
        if value is None:
            return False
        if isinstance(value, str):
            return value.strip() != ""
        if isinstance(value, (list, tuple)):
            return len(value) > 0
        return True

    @staticmethod
    def _text_answer_cap(question) -> int | None:
        """The character budget a text question actually enforces.

        `short_text` has no length configuration and never will: choosing that
        type is the author's statement about length. `long_text` takes the
        author's budget when they set one and the hard ceiling when they did
        not, so no text question is ever unbounded.

        Args:
            question (dict): One question out of the form schema, in the
                camelCase shape the JSONB column stores.

        Returns:
            int | None: The budget, or None for a question that is not text.
        """
        qtype = question.get("type")
        if qtype == "short_text":
            return SHORT_TEXT_MAX_LENGTH
        if qtype == "long_text":
            authored = question.get("maxLength")
            return LONG_TEXT_MAX_LENGTH if authored is None else authored
        return None

    @classmethod
    def _question_value_error(cls, question, value) -> str | None:
        """Why an answer does not fit the question that was asked, if it does not.

        The form's own constraints -- an option list, a selection cap, a
        length budget, a phrase to type back -- were authored and validated
        but never enforced against a submission. Enforcing them here rather
        than only in the browser matters twice over: the API accepts any JSON
        for an answer, and a choice value outside the option list also decides
        whether the questions that one gates are shown at all, so an
        unconstrained value could hide a required question instead of
        answering it.

        Args:
            question (dict): One question out of the form schema.
            value: The recorded answer, already known to be non-empty.

        Returns:
            str | None: A message naming the question, or None when the
                answer fits.
        """
        label = question.get("label") or question.get("id")
        qtype = question.get("type")
        options = question.get("options") or []

        if qtype == "single_choice" and value not in options:
            return f"{label}: pick one of the listed options"
        if qtype == "multi_choice":
            if not isinstance(value, list):
                return f"{label}: pick from the listed options"
            if any(v not in options for v in value):
                return f"{label}: pick from the listed options"
            cap = question.get("maxSelections")
            if cap is not None and len(value) > cap:
                return f"{label}: pick at most {cap}"
        cap = cls._text_answer_cap(question)
        if cap is not None and len(str(value)) > cap:
            return f"{label}: keep this under {cap} characters"
        if qtype == "exact_text":
            expected = question.get("expectedValue") or ""
            if str(value).strip() != expected:
                return f"{label}: type {expected} exactly"
        return None

    def _validate_submission(self, job, dto) -> None:
        """Enforce what the posting asks of a submission.

        ``required`` is enforced only on the questions the form was actually
        showing: a required question gated behind a showWhen rule is not
        displayed once the rule stops matching, so demanding an answer for it
        would leave the candidate unable to submit a form they have filled in
        completely.

        Messages name a question by its label, not its id. They reach the
        candidate verbatim, and ``q7`` appears nowhere on the page they are
        looking at.

        Args:
            job (JobEntity): The posting the submission is for.
            dto (ApplicationSubmitDto | ApplicationEditDto): The payload.

        Raises:
            ValueError: If a required résumé, profile section or answer is
                missing, or an answer does not fit the question asked.
        """
        profile_config = job.profile_config or {}
        if profile_config.get("resume") == "required" and not dto.resume_object_key:
            raise ValueError("this posting requires a résumé")
        # Both sections carry a required marker in the form; nothing held the
        # submission to it.
        if profile_config.get("education") == "required" and not dto.education:
            raise ValueError("this posting requires at least one education entry")
        if profile_config.get("workExperience") == "required" and not dto.experience:
            raise ValueError("this posting requires at least one experience entry")

        personal = dto.personal or {}
        for key, needed in _REQUIRED_PERSONAL:
            if self._blank(personal.get(key)):
                raise ValueError(f"your application needs {needed}")

        # Rows are checked wherever they are shown -- an `optional` section
        # means "you need not add one", not "a half-filled one is fine". A
        # section switched `off` is skipped: it is not rendered, so a problem
        # there could never be seen, let alone fixed.
        #
        # Deliberately only the presence rules, not the ordering ones the form
        # also applies (a start date in the future, an end before a start).
        # Those live in the browser alone, as they always have on the Profile
        # page; mirroring them here would mean parsing the form's month names
        # in Python for no protection that matters.
        for section, rows, fields in (
            ("education", dto.education, _EDUCATION_FIELDS),
            ("experience", dto.experience, _EXPERIENCE_FIELDS),
        ):
            if profile_config.get(_SECTION_CONFIG_KEY[section]) == "off":
                continue
            for index, row in enumerate(rows or [], start=1):
                problem = self._row_problem(row, fields)
                if problem is not None:
                    # Numbered, not keyed: the row's `rpf-9` id appears nowhere
                    # on the page the candidate is looking at.
                    raise ValueError(f"{section} entry {index}: {problem}")

        for question in form_visibility.visible_questions(job.form_schema, dto.answers):
            label = question.get("label") or question.get("id")
            value = dto.answers.get(question["id"])
            if not self._answered(value):
                if question.get("required"):
                    raise ValueError(f"{label} is required")
                continue
            problem = self._question_value_error(question, value)
            if problem is not None:
                raise ValueError(problem)
            # The renderer marks the "Other" free text required whenever that
            # option is picked, and until now nothing held it to that.
            if form_visibility.other_selected(question, value) and not self._answered(
                dto.answers.get(f"{question['id']}{form_visibility.OTHER_SUFFIX}")
            ):
                raise ValueError(f"{label}: describe your answer")

    @staticmethod
    def _blank(value) -> bool:
        """Missing, or nothing but whitespace."""
        return not str(value or "").strip()

    @classmethod
    def _row_problem(cls, row, fields) -> str | None:
        """What is missing from one education or experience row, if anything.

        Args:
            row (dict): One row in the form's shape.
            fields (tuple): (key, human name) pairs that must be filled in.

        Returns:
            str | None: A phrase naming the first gap, or None when the row is
                a real entry.
        """
        entry = row or {}
        for key, name in fields:
            if cls._blank(entry.get(key)):
                return f"{name} is required"
        if cls._blank(entry.get("startMonth")) or cls._blank(entry.get("startYear")):
            return "a start date is required"
        # A role still held has no end to give; the form hides the field.
        if entry.get("isCurrentlyWorking"):
            return None
        if cls._blank(entry.get("endMonth")) or cls._blank(entry.get("endYear")):
            return "an end date is required"
        return None

    @staticmethod
    def _prune_hidden_answers(job, dto) -> None:
        """Drop answers the form was not showing at write time.

        Runs before screening and before the snapshot is built, so a rule and
        a reviewer both see the same answers the candidate last stood behind.
        Called after ``_validate_submission`` so both resolve visibility
        against the same submitted answers.

        Args:
            job (JobEntity): The posting the submission is for.
            dto (ApplicationSubmitDto | ApplicationEditDto): The payload,
                mutated in place.
        """
        dto.answers = form_visibility.prune_answers(job.form_schema, dto.answers)

    @staticmethod
    def _strip_uncollected_sections(job, dto) -> None:
        """Drop profile rows for a section the posting doesn't collect.

        The sibling of ``_strip_uncollected_resume``, for the same reason. A
        ``profile_config`` section set to ``"off"`` is not rendered at all, so
        rows still attached to the payload were never on the candidate's
        screen -- they came from a résumé parse, which autofills regardless, or
        from an older submission. Keeping them would store data nobody
        reviewed, and a later profile write-back could push it into the
        candidate's profile, replacing rows they never saw.

        Stripped rather than rejected, again like the résumé: the candidate did
        nothing wrong, and there is nothing for them to fix.

        Args:
            job (JobEntity): The posting the submission is for.
            dto (ApplicationSubmitDto | ApplicationEditDto): Mutated in place.
        """
        profile_config = job.profile_config or {}
        if profile_config.get(_SECTION_CONFIG_KEY["education"]) == "off":
            dto.education = []
        if profile_config.get(_SECTION_CONFIG_KEY["experience"]) == "off":
            dto.experience = []

    @staticmethod
    def _strip_uncollected_resume(job, dto) -> None:
        """Drop resume keys when the posting doesn't collect a resume.

        A ``profile_config.resume == "off"`` posting treats an upload as
        prefill-only (the parser autofills the form client-side); the file
        reference must never be persisted onto the submission. Enforced
        server-side too so a direct API call can't attach one.

        Args:
            job (JobEntity): The posting the submission is for.
            dto (ApplicationSubmitDto | ApplicationEditDto): Mutated in place.
        """
        if (job.profile_config or {}).get("resume") == "off":
            dto.resume_object_key = None
            dto.resume_sha256 = None

    @staticmethod
    def _screened_stage(job, blocked, screen_action):
        """The stage a submission lands on.

        Args:
            job (JobEntity): The posting being submitted to.
            blocked (bool): Whether the applicant is blacklisted.
            screen_action (str | None): ``"reject"`` | ``"qualify"`` |
                ``"auto_hire"`` | None — the outcome of
                ``screen_rules.evaluate()`` (always None when ``blocked``,
                since a blacklist entry is evaluated first and wins
                outright).

        Returns:
            ApplicationStage: ``REJECTED`` when blocked or a ``"reject"``
                rule matched; ``HIRED`` when an ``"auto_hire"`` rule
                matched; otherwise the job's first configured pipeline
                stage (unscreened and ``"qualify"`` both land here
                identically).
        """
        if blocked or screen_action == "reject":
            return ApplicationStage.REJECTED
        if screen_action == "auto_hire":
            return ApplicationStage.HIRED
        return stage_machine.first_stage(job.pipeline_config)

    @staticmethod
    def _screened_sub_status(stage):
        """The sub_status for a just-landed stage.

        Mirrors ``BoardService.change_stage``'s rule: ``"pending"`` for a
        real configurable pipeline stage, ``None`` for a terminal stage
        (``REJECTED``/``HIRED`` have no sub-status concept).

        Args:
            stage (ApplicationStage): The stage just landed on.

        Returns:
            str | None: ``"pending"`` or ``None``.
        """
        if stage in (ApplicationStage.REJECTED, ApplicationStage.HIRED):
            return None
        return "pending"

    @staticmethod
    def _screened_tags(blocked, screen_action, screen_rule_id):
        """The tags to store for a blocked/screen-rule-rejected outcome.

        Args:
            blocked (bool): Whether the applicant is blacklisted.
            screen_action (str | None): See ``_screened_stage``.
            screen_rule_id (str | None): The matched rule's id, if any.

        Returns:
            dict | None: ``{"auto_reject": "blocked"}`` when blocked,
                ``{"auto_reject": "screen_rule", "rule_id": ...}`` when a
                ``"reject"`` rule matched, else None (the caller falls
                back to any other tag it would otherwise set, e.g. a
                cooldown ``cold_freeze`` marker).
        """
        if blocked:
            return {"auto_reject": "blocked"}
        if screen_action == "reject":
            return {"auto_reject": "screen_rule", "rule_id": screen_rule_id}
        return None

    async def submit(
        self,
        session: AsyncSession,
        current_user: UserContextDto,
        dto: ApplicationSubmitDto,
    ) -> ApplicationDto:
        """Create/land an application (or auto-screen it, or auto-reject a
        blocked user).

        Logs an ``"application_submitted"`` (or, for a blocked applicant or
        a screen-rule ``"reject"`` match, ``"auto_rejected"``) entry to the
        audit timeline on every call, attributed to the candidate
        themselves — covers a fresh submission, a reapply after cooldown,
        and a blocked/screen-rejected outcome alike. Independent of the
        blacklist check, a matching ``screen_rules`` rule can also land the
        submission on ``REJECTED`` (a ``"reject"`` match) or ``HIRED`` (an
        ``"auto_hire"`` match) with zero human review; a ``"qualify"``
        match proceeds exactly as an unscreened submission would, with a
        note added to the activity log.

        A re-apply after rejection creates a fresh application row rather
        than reusing the rejected one: prior attempts are immutable
        history, kept exactly as they were rejected (own stage, tags, and
        submission snapshots untouched), while the new attempt starts a
        brand-new version-1 submission.

        Args:
            session (AsyncSession): Active database async session.
            current_user (UserContextDto): The authenticated applicant.
            dto (ApplicationSubmitDto): The submission payload.

        Returns:
            ApplicationDto: The persisted application with its current version.

        Raises:
            ValueError: If the posting is missing or not live to candidates
                (see ``PUBLICLY_VISIBLE_JOB_STATUSES`` -- a pending revision or
                close review does not stop submissions), a required
                résumé/answer is missing, or the latest existing application
                for this job is not REJECTED (an active application must be
                edited instead of resubmitted).
        """
        job = await self.job_repository.get_by_job_id(session, dto.job_id)
        if job is None or job.status not in PUBLICLY_VISIBLE_JOB_STATUSES:
            raise ValueError(f"Published job {dto.job_id} not found")
        self._validate_submission(job, dto)
        self._prune_hidden_answers(job, dto)
        self._strip_uncollected_resume(job, dto)
        self._strip_uncollected_sections(job, dto)

        user = await self.users_repository.get_user_by_user_id(
            session, current_user.user_id
        )
        blocked = bool(user is not None and getattr(user, "is_blocked", False))
        applicant_email_rows = (
            await self.user_emails_repository.list_by_user_id(
                session, current_user.user_id
            )
            if not blocked
            else []
        )
        # Screen against every confirmed claim, not just the contact
        # address — a corp email held as a non-primary claim must still
        # satisfy (or escape) email_domain rules. Unconfirmed claims are
        # excluded so an unverified address can't game the screening.
        applicant_emails = [
            row.email for row in applicant_email_rows if row.otp_confirmed
        ]
        screen_result = (
            {"action": None, "rule_id": None}
            if blocked
            else screen_rules.evaluate(
                job.screen_rules,
                applicant_emails,
                dto.answers,
            )
        )
        screen_action = screen_result["action"]
        screen_rule_id = screen_result["rule_id"]

        existing = await self.application_repository.get_latest_by_job_and_user(
            session, dto.job_id, current_user.user_id
        )
        if existing is not None and existing.stage != ApplicationStage.REJECTED:
            raise ValueError(
                "you already have an application for this job; edit it instead"
            )

        stage = self._screened_stage(job, blocked, screen_action)
        tags = self._screened_tags(blocked, screen_action, screen_rule_id)
        if existing is not None and tags is None and stage != ApplicationStage.HIRED:
            # Re-apply after a rejection: carry the advisory cold_freeze tag
            # when the new attempt lands inside the job's cooldown window.
            # Anchored to the prior row's last-update time (when it was moved
            # to REJECTED), not its submitted_at, which can predate it. An
            # auto_hire landing (HIRED) or an auto-reject tag supersedes it,
            # same precedence as before.
            rejected_at = (
                existing.updated_timestamp or existing.created_datetime
            ).date()
            thaw = cooldown.compute_thaw(rejected_at, job.cooldown_days)
            if cooldown.is_in_cooldown(self._today(), thaw):
                tags = {"cold_freeze": {"thaw_date": thaw.isoformat()}}

        application = await self.application_repository.create(
            session,
            ApplicationEntity(
                job_id=dto.job_id,
                user_id=current_user.user_id,
                stage=stage,
                stage_entered_at=datetime.now(timezone.utc),
                sub_status=self._screened_sub_status(stage),
                tags=tags,
            ),
        )
        current_sub = await self._write_version(
            session, application.application_id, 1, None, dto, job
        )

        await self._assign_default_if_configured(
            session, application, job, current_user
        )

        if stage == ApplicationStage.HIRED:
            await self.onboarding_training_service.ensure_for_admitted(
                session=session,
                user_id=current_user.user_id,
                job=job,
            )

        if blocked:
            # actor_id is None because the rules did this, not a person. The
            # request that triggered it comes from the *candidate*, so passing
            # current_user here would tell our own staff that the applicant
            # rejected the applicant. The copy also selects its "happened
            # automatically" wording on actor_name being None.
            await record_event(
                session,
                subject_type="application",
                subject_id=application.application_id,
                actor_id=None,
                event_type=RecruitingEvent.AUTO_REJECTED,
                details={"reason": "blocked"},
            )
        elif screen_action == "reject":
            await record_event(
                session,
                subject_type="application",
                subject_id=application.application_id,
                actor_id=None,
                event_type=RecruitingEvent.AUTO_REJECTED,
                details={"reason": "screen_rule", "ruleId": screen_rule_id},
            )
        else:
            details = {"stage": application.stage.value}
            if screen_action == "qualify":
                details["screenQualifyRuleId"] = screen_rule_id
            elif screen_action == "auto_hire":
                details["screenAutoHireRuleId"] = screen_rule_id
            await record_event(
                session,
                subject_type="application",
                subject_id=application.application_id,
                actor_id=current_user.user_id,
                event_type=RecruitingEvent.APPLICATION_SUBMITTED,
                details=details,
            )

        await session.commit()
        lock_reason = self._lock_reason(application, job, current_sub)
        return self.recruiting_mapper.to_application_dto(
            application,
            current_sub,
            editable=lock_reason is None,
            lock_reason=lock_reason,
        )

    async def _rescreen_after_edit(
        self, session, current_user, application, job, dto
    ) -> None:
        """Re-run machine screening against the answers an edit just stored.

        An edit is not a draft: the candidate has no save that is not a
        submission, so the answers this writes are the answers the posting is
        being applied to. Screening them only the first time left a rule the
        edit now matches unfired -- answer "yes" to the question that
        auto-rejects, submit, then edit it to "no", and the application stayed
        in the pipeline reading "no" with nothing having looked at it.

        All three outcomes apply, the same as on submit, so the result is a
        function of the recorded answers and not of which write recorded them.

        The blacklist is deliberately not re-checked here: it is swept
        separately across every application (see ``BlacklistService``), and
        that sweep, not an applicant's own edit, is what should act on it.

        Args:
            session (AsyncSession): Active database async session.
            current_user (UserContextDto): The authenticated applicant.
            application (ApplicationEntity): The row being edited, already
                locked by ``edit``.
            job (JobEntity): The posting applied to.
            dto (ApplicationEditDto): The edit payload, post-validation.
        """
        applicant_email_rows = await self.user_emails_repository.list_by_user_id(
            session, current_user.user_id
        )
        applicant_emails = [
            row.email for row in applicant_email_rows if row.otp_confirmed
        ]
        result = screen_rules.evaluate(job.screen_rules, applicant_emails, dto.answers)
        action, rule_id = result["action"], result["rule_id"]
        if action is None or action == "qualify":
            # "qualify" lands on the first stage on submit, which is where an
            # editable application already sits. Nothing to move.
            return

        if action == "reject":
            application.stage = ApplicationStage.REJECTED
            application.stage_entered_at = datetime.now(timezone.utc)
            application.sub_status = self._screened_sub_status(
                ApplicationStage.REJECTED
            )
            application.tags = {"auto_reject": "screen_rule", "rule_id": rule_id}
            await self.application_repository.update(session, application)
            await record_event(
                session,
                subject_type="application",
                subject_id=application.application_id,
                actor_id=None,
                event_type=RecruitingEvent.AUTO_REJECTED,
                details={"reason": "screen_rule", "ruleId": rule_id, "onEdit": True},
            )
        else:  # auto_hire
            application.stage = ApplicationStage.HIRED
            application.stage_entered_at = datetime.now(timezone.utc)
            application.sub_status = self._screened_sub_status(ApplicationStage.HIRED)
            await self.application_repository.update(session, application)
            await record_event(
                session,
                subject_type="application",
                subject_id=application.application_id,
                actor_id=current_user.user_id,
                event_type=RecruitingEvent.APPLICATION_SUBMITTED,
                details={
                    "stage": ApplicationStage.HIRED.value,
                    "screenAutoHireRuleId": rule_id,
                    "onEdit": True,
                },
            )
            await self.onboarding_training_service.ensure_for_admitted(
                session=session,
                user_id=current_user.user_id,
                job=job,
            )

    async def _assign_default_if_configured(
        self, session, application, job, current_user
    ):
        """Materialize a stage's configured default assignee into a real row.

        A stage's ``defaultAssigneeId`` is only a board-display fallback
        (``BoardService.get_board`` shows it on the card) until a real
        ``application_assignment`` row exists — ``My Interview Evaluations`` and
        evaluation submit/read only see real rows. Without this, an
        application landing directly on a stage with a configured default
        (recruiter_screening on submission, or any stage after a reapply)
        would show "Assigned to: X" on the board while X's own "My
        Evaluations" stayed empty forever, since nothing else ever creates
        that row for the entry stage.

        No-ops for a non-interview stage (e.g. a blocked applicant's
        REJECTED landing), a stage with no default configured, or a job with
        no configured owner (nothing sensible to attribute ``assigned_by``
        to — mirrors the pre-existing "no owner" board-visibility gap rather
        than raising). Logs an ``"auto_assigned"`` activity entry, attributed
        to the submitting candidate, only on the path where a row is
        actually materialized.

        Args:
            session (AsyncSession): Active database async session.
            application (ApplicationEntity): The just-landed application.
            job (JobEntity): Its posting, for pipeline_config lookup.
            current_user (UserContextDto): The submitting candidate, recorded
                as the activity entry's actor.
        """
        if application.stage not in INTERVIEW_STAGES:
            return
        default_id = None
        for entry in (job.pipeline_config or {}).get("stages") or []:
            if (
                isinstance(entry, dict)
                and entry.get("stage") == application.stage.value
            ):
                default_id = entry.get("defaultAssigneeId")
                break
        if default_id is None:
            return
        owner_ids = normalized_owner_ids(job.pipeline_config)
        if not owner_ids:
            return
        await self.application_assignment_repository.upsert(
            session,
            application.application_id,
            application.stage,
            application.current_round,
            default_id,
            owner_ids[0],
        )
        # actor_id is None for the same reason as the automatic rejections
        # above: the pipeline's default-assignee rule did this, and the
        # request behind it is the candidate's.
        await record_event(
            session,
            subject_type="application",
            subject_id=application.application_id,
            actor_id=None,
            event_type=RecruitingEvent.AUTO_ASSIGNED,
            details={
                "stage": application.stage.value,
                "assigneeId": default_id,
                "round": application.current_round,
            },
        )

    async def edit(
        self,
        session: AsyncSession,
        current_user: UserContextDto,
        application_id: int,
        dto: ApplicationEditDto,
    ) -> ApplicationDto:
        """Overwrite the current submission version while still Applied.

        Row-locks the application for the duration of the transaction so a
        concurrent owner decision (freeze/advance via ``BoardService``)
        can't interleave with this edit — without the lock, an edit could
        silently overwrite the submission a decision was already based on.
        ``_lock_reason`` is evaluated after this locked load, on the
        now-current row.

        Args:
            session (AsyncSession): Active database async session.
            current_user (UserContextDto): The authenticated applicant.
            application_id (int): The application to edit.
            dto (ApplicationEditDto): The edit payload.

        Returns:
            ApplicationDto: The persisted application with its current version.

        Raises:
            ValueError: If not the owner, the application is no longer
                editable (processing has started), or a required
                résumé/answer is missing.
        """
        application = await self._load_owned(
            session, current_user, application_id, for_update=True
        )
        job = await self.job_repository.get_by_job_id(session, application.job_id)
        current_sub = await self.application_submission_repository.get_current(
            session, application_id
        )
        if self._lock_reason(application, job, current_sub) is not None:
            raise ValueError("application is locked once processing has started")
        self._validate_submission(job, dto)
        self._prune_hidden_answers(job, dto)
        self._strip_uncollected_resume(job, dto)
        self._strip_uncollected_sections(job, dto)
        version = current_sub.version if current_sub is not None else 1
        current_sub = await self._write_version(
            session, application_id, version, current_sub, dto, job
        )
        await self._rescreen_after_edit(session, current_user, application, job, dto)
        await session.commit()
        lock_reason = self._lock_reason(application, job, current_sub)
        return self.recruiting_mapper.to_application_dto(
            application,
            current_sub,
            editable=lock_reason is None,
            lock_reason=lock_reason,
        )

    async def get_my_latest_profile(self, session, current_user: UserContextDto):
        """The profile blocks of this candidate's most recent submission.

        What the application form falls back to when the candidate's profile
        has nothing for a block: someone who applied once without saving to
        their profile should not have to retype it for the next posting.

        Only the profile blocks. Answers belong to the job they were asked
        for -- prefilling another posting's answers would be wrong, whatever
        the questions happened to be.

        Args:
            session (AsyncSession): The active DB session.
            current_user (UserContextDto): The caller, who can only ever read
                their own submissions here.

        Returns:
            dict: `personal`, `education` and `experience`, empty when the
                candidate has never submitted anything.
        """
        latest = await self.application_submission_repository.get_latest_by_user(
            session, current_user.user_id
        )
        submission = (latest.submission if latest is not None else None) or {}
        return {
            "personal": submission.get("personal") or {},
            "education": submission.get("education") or [],
            "experience": submission.get("experience") or [],
        }

    async def get_mine(
        self, session: AsyncSession, current_user: UserContextDto, job_id: int
    ) -> ApplicationDto | None:
        """Return the caller's application for a job, or None.

        Args:
            session (AsyncSession): Active database async session.
            current_user (UserContextDto): The authenticated applicant.
            job_id (int): The posting to look up.

        Returns:
            ApplicationDto | None: The caller's application, or None if absent.
        """
        application = await self.application_repository.get_latest_by_job_and_user(
            session, job_id, current_user.user_id
        )
        if application is None:
            return None
        current_sub = await self.application_submission_repository.get_current(
            session, application.application_id
        )
        job = await self.job_repository.get_by_job_id(session, application.job_id)
        lock_reason = self._lock_reason(application, job, current_sub)
        return self.recruiting_mapper.to_application_dto(
            application,
            current_sub,
            editable=lock_reason is None,
            lock_reason=lock_reason,
        )

    async def list_mine(self, session, current_user) -> list:
        """Return every application the caller has ever submitted, any job kind.

        Args:
            session (AsyncSession): Active database async session.
            current_user (UserContextDto): The authenticated applicant.

        Returns:
            list[MyApplicationSummaryDto]: One row per application, in the
                order `ApplicationRepository.list_by_user` returns them.
        """
        rows = await self.application_repository.list_by_user(
            session, current_user.user_id
        )
        return [
            self.recruiting_mapper.to_my_application_summary_dto(application, job)
            for application, job in rows
        ]

    def _lock_reason(self, application, job, current_submission):
        """Why the candidate can no longer edit, or None while they still can.

        ``editable`` is derived from this rather than computed beside it, so a
        client cannot be told it is locked and shown no reason, or the reverse.

        ADVANCED is checked first because it is the more informative answer:
        naming where the application went tells the reader more than saying
        someone is working on it.

        Args:
            application (ApplicationEntity): The application container.
            job (JobEntity): The posting the application is for.
            current_submission (ApplicationSubmissionEntity | None): The
                application's current (highest) submission version.

        Returns:
            ApplicationLockReason | None: The reason editing is closed, or
                None while the application sits at the job's first configured
                stage with a pending sub_status and an unfrozen submission.
        """
        if application.stage != stage_machine.first_stage(job.pipeline_config):
            return ApplicationLockReason.ADVANCED
        if (application.sub_status or "pending") != "pending":
            return ApplicationLockReason.IN_REVIEW
        if current_submission is not None and current_submission.is_frozen:
            return ApplicationLockReason.IN_REVIEW
        return None

    async def _load_owned(
        self, session, current_user, application_id, *, for_update: bool = False
    ):
        """Fetch an application and assert the caller owns it.

        Args:
            session (AsyncSession): Active database async session.
            current_user (UserContextDto): The authenticated applicant.
            application_id (int): The application to fetch.
            for_update (bool): When True, row-locks the application
                (``SELECT ... FOR UPDATE``) so a concurrent owner decision
                (freeze/advance) on the same application can't interleave
                with this call. ``edit`` passes True (it mutates); read-only
                callers should leave this False.

        Returns:
            ApplicationEntity: The owned application.

        Raises:
            ValueError: If missing or owned by another user.
        """
        application = await self.application_repository.get_by_id(
            session, application_id, for_update=for_update
        )
        if application is None or application.user_id != current_user.user_id:
            raise ValueError(f"application {application_id} not found")
        return application

    async def _write_version(
        self, session, application_id, version, current_sub, dto, job
    ):
        """Overwrite the current version in place, or create version 1.

        Args:
            session (AsyncSession): Active database async session.
            application_id (int): The owning application.
            version (int): The version number to write.
            current_sub (ApplicationSubmissionEntity | None): The existing
                current version, or None to create version 1.
            dto (ApplicationSubmitDto | ApplicationEditDto): The payload.
            job (JobEntity): The posting being applied to, read for its
                live ``form_schema`` to snapshot.

        Returns:
            ApplicationSubmissionEntity: The persisted submission version.
        """
        snapshot = self._snapshot(dto, job)
        if current_sub is None:
            return await self.application_submission_repository.create(
                session,
                ApplicationSubmissionEntity(
                    application_id=application_id,
                    version=version,
                    submission=snapshot,
                    resume_object_key=dto.resume_object_key,
                    resume_sha256=dto.resume_sha256,
                ),
            )
        current_sub.submission = snapshot
        current_sub.resume_object_key = dto.resume_object_key
        current_sub.resume_sha256 = dto.resume_sha256
        return await self.application_submission_repository.update(session, current_sub)
