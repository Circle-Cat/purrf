"""Recruiting interview-meeting scheduling (thin domain controller).

Owns the recruiting rules — who may book, which stages can be booked, which
assignment row the meeting belongs to, what the application's sub_status
becomes — and delegates every Google call to the shared
``MeetingSchedulingService``.
"""

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.exceptions import MeetingGoneError
from backend.common.name_utils import display_name_of
from backend.common.recruiting_enums import ApplicationStage, RecruitingEvent
from backend.dto.interview_dto import InterviewDto, InterviewScheduleRequestDto
from backend.dto.user_context_dto import UserContextDto
from backend.notification_management.event_recorder import record_event

# Only these two stages meet the candidate; recruiter screening and board
# review evaluate on materials alone (their assignees are still evaluators —
# they just never book a meeting).
SCHEDULABLE_STAGES = (ApplicationStage.BEHAVIORAL, ApplicationStage.TECH)

_STAGE_TITLES = {
    ApplicationStage.BEHAVIORAL: "Behavioral",
    ApplicationStage.TECH: "Technical",
}

# The meeting title's second segment. Fixed, not the job title: attendees
# already know which posting they applied to, and the recruiter's inbox
# fills with lookalike titles otherwise; "Ana/Circle Cat, Behavioral" is
# unambiguous at a glance across every posting.
_COMPANY_NAME = "Circle Cat"

_MEETING_GONE_MESSAGE = (
    "This meeting no longer exists on the calendar. Cancel it here and "
    "schedule a new one."
)


def _to_utc(day, start_time, duration_minutes, timezone_name):
    """Wall-clock (date, HH:MM, zone) -> tz-aware UTC start/end.

    Built by attaching the zone to a naive local datetime so the offset comes
    from the zone's rules on that date — the same wall-clock contract
    mentorship uses. Subtracting a fixed offset would silently shift meetings
    booked across a DST change.
    """
    hour, minute = (int(part) for part in start_time.split(":"))
    naive = datetime(day.year, day.month, day.day, hour, minute)
    start_utc = naive.replace(tzinfo=ZoneInfo(timezone_name)).astimezone(
        ZoneInfo("UTC")
    )
    return start_utc, start_utc + timedelta(minutes=duration_minutes)


def _meeting_title(candidate_first_name: str, stage: ApplicationStage) -> str:
    """The Calendar event summary attendees see, e.g. "Ana/Circle Cat, Behavioral".

    No round suffix — the round is visible on the board/detail page, and a
    later round reuses the exact same title so the calendar entry reads the
    same regardless of which attempt this is.
    """
    return f"{candidate_first_name}/{_COMPANY_NAME}, {_STAGE_TITLES[stage]}"


def _staff_name(user) -> str | None:
    """The interviewer/scheduler name, or None when the row is gone.

    They are colleagues, so the preferred name wins. The candidate is named
    separately by ``_meeting_title``, which keeps their legal first name.
    """
    if user is None:
        return None
    return display_name_of(user)


class InterviewSchedulingService:
    """Book/reschedule/cancel a recruiting interview's Calendar meeting.

    Every mutation is owner-gated the same way ``BoardService``'s other
    mutation paths are, via the shared ``ApplicationAccess`` collaborator —
    not by importing ``BoardService`` — so job ownership and the
    interview-evaluator check stay in exactly one place.
    """

    def __init__(
        self,
        logger,
        application_access,
        application_repository,
        application_assignment_repository,
        application_interview_repository,
        users_repository,
        user_emails_repository,
        meeting_scheduling_service,
        recruiting_mapper,
        interview_calendar_id,
    ):
        """
        Args:
            logger (Logger): Shared app logger.
            application_access (ApplicationAccess): Shared owner/assignee
                gating and interview-evaluator validation, also injected
                into ``BoardService``.
            application_repository (ApplicationRepository): Application data
                access, for the sub_status write on schedule/cancel.
            application_assignment_repository (ApplicationAssignmentRepository):
                Per-(application, stage, round) interviewer assignment data
                access; the meeting's assignee IS the round's assignment.
            application_interview_repository (ApplicationInterviewRepository):
                Scheduled-meeting row data access.
            users_repository (UsersRepository): Candidate/interviewer/
                recruiter name resolution for the meeting title and the
                response DTO.
            user_emails_repository (UserEmailsRepository): Candidate
                contact-email presence check (a hard reject when missing).
            meeting_scheduling_service (MeetingSchedulingService): The
                domain-agnostic Google Calendar/Meet transport.
            recruiting_mapper (RecruitingMapper): Entity->DTO conversion.
            interview_calendar_id (str): The Google Calendar interview meetings
                are created on, patched on and deleted from. Per-environment:
                cancellation here is automation-driven (advance / reject /
                blacklist, and the blacklist sweep covers every application),
                so a shared calendar would let one environment delete another
                environment's real interviews in bulk.
        """
        self.logger = logger
        self.application_access = application_access
        self.application_repository = application_repository
        self.application_assignment_repository = application_assignment_repository
        self.application_interview_repository = application_interview_repository
        self.users_repository = users_repository
        self.user_emails_repository = user_emails_repository
        self.meeting_scheduling_service = meeting_scheduling_service
        self.recruiting_mapper = recruiting_mapper
        self.interview_calendar_id = interview_calendar_id

    async def schedule(
        self,
        session: AsyncSession,
        current_user: UserContextDto,
        application_id: int,
        dto: InterviewScheduleRequestDto,
    ) -> InterviewDto:
        """Book a Calendar meeting for an application's current stage+round.

        Order matters: every recruiting-side validation happens BEFORE the
        Calendar call, and the Calendar call happens BEFORE the interview row
        and the application's sub_status are written — a failed booking must
        leave zero new rows and an untouched sub_status. See the module
        docstring's design note for why.

        Args:
            session (AsyncSession): Active database async session.
            current_user (UserContextDto): The authenticated caller (the
                acting recruiter, invited to the meeting and recorded as
                ``scheduled_by``).
            application_id (int): The application to book a meeting for.
            dto (InterviewScheduleRequestDto): The requested slot and
                interviewer, in the recruiter's own wall-clock terms.

        Returns:
            InterviewDto: The newly booked meeting.

        Raises:
            ValueError: If the application is missing/not owned, its current
                stage isn't schedulable, its current round already has a
                meeting booked, the proposed assignee doesn't hold
                ``RECRUITING_INTERVIEW_EVALUATE``, or the candidate has no
                contact email on file.
        """
        application, _job = await self.application_access.load_owned_application(
            session, current_user, application_id, for_update=True
        )
        if application.stage not in SCHEDULABLE_STAGES:
            raise ValueError(
                "Only behavioral and technical interviews can be scheduled."
            )
        existing = await self.application_interview_repository.get(
            session, application_id, application.stage, application.current_round
        )
        if existing is not None:
            raise ValueError("This session already has an interview meeting scheduled.")
        await self.application_access.validate_interview_assignee(
            session, dto.assignee_id
        )
        # Hard reject, unlike MeetingSchedulingService.resolve_attendee_emails'
        # own "skip a missing address with a warning" default (see its
        # docstring: "callers for whom a missing address is fatal must check
        # that themselves"). The candidate IS that fatal case: a meeting the
        # candidate never gets invited to is pointless, whereas a missing
        # interviewer/recruiter address is merely degraded (they can still
        # be reached some other way) -- so only the candidate is checked here.
        contact_by_user_id = (
            await self.user_emails_repository.get_contact_emails_by_user_ids(
                session, [application.user_id]
            )
        )
        if not contact_by_user_id.get(application.user_id):
            raise ValueError("This candidate has no email address on file.")

        await self.application_assignment_repository.upsert(
            session,
            application_id,
            application.stage,
            application.current_round,
            dto.assignee_id,
            current_user.user_id,
        )

        candidate = await self.users_repository.get_user_by_user_id(
            session, application.user_id
        )
        summary = _meeting_title(
            candidate.first_name if candidate is not None else "",
            application.stage,
        )
        start_utc, end_utc = _to_utc(
            dto.date, dto.start_time, dto.duration_minutes, dto.timezone
        )
        attendee_ids = [application.user_id, dto.assignee_id, current_user.user_id]
        try:
            meeting = await self.meeting_scheduling_service.schedule(
                session,
                summary,
                start_utc,
                end_utc,
                attendee_ids,
                calendar_id=self.interview_calendar_id,
            )
        except Exception as e:
            self.logger.error(
                "[InterviewSchedulingService] Calendar booking failed for "
                "application_id=%s: %s",
                application_id,
                e,
            )
            raise

        interview = await self.application_interview_repository.create(
            session,
            application_id=application_id,
            stage=application.stage,
            round=application.current_round,
            google_event_id=meeting["google_event_id"],
            meet_link=meeting.get("meet_link") or None,
            start_at=start_utc,
            end_at=end_utc,
            scheduled_by=current_user.user_id,
        )
        # Unconditional -- unlike cancel()'s `if sub_status == "scheduled"`
        # guard below. The two are asymmetric on purpose: booking a NEW
        # meeting means another interview is genuinely about to happen, so
        # moving even an "evaluated" round forward to "scheduled" is correct
        # progress (e.g. a redo after `reassign`). Cancelling a past,
        # already-evaluated interview's calendar entry must NOT erase that
        # evaluation progress, which is why that path only reverts from
        # exactly "scheduled".
        application.sub_status = "scheduled"
        await self.application_repository.update(session, application)
        await record_event(
            session,
            subject_type="application",
            subject_id=application_id,
            actor_id=current_user.user_id,
            event_type=RecruitingEvent.INTERVIEW_SCHEDULED,
            details={
                "stage": application.stage.value,
                "round": application.current_round,
                "assigneeId": dto.assignee_id,
                "startAt": start_utc.isoformat(),
                "endAt": end_utc.isoformat(),
                "timezone": dto.timezone,
                "googleEventId": meeting["google_event_id"],
            },
        )
        await session.commit()

        assignee = await self.users_repository.get_user_by_user_id(
            session, dto.assignee_id
        )
        scheduler = await self.users_repository.get_user_by_user_id(
            session, current_user.user_id
        )
        return self.recruiting_mapper.to_interview_dto(
            interview,
            assignee_id=dto.assignee_id,
            assignee_name=_staff_name(assignee),
            scheduled_by_name=_staff_name(scheduler),
        )

    async def update(
        self,
        session: AsyncSession,
        current_user: UserContextDto,
        application_id: int,
        dto: InterviewScheduleRequestDto,
    ) -> InterviewDto:
        """Move an already-booked meeting's time and/or swap its interviewer.

        No past/future branch: the invariant "the assignment and the
        calendar never diverge" is worth more than avoiding an odd
        notification for a meeting whose time has already passed.

        ``scheduled_by`` is never touched here (see
        ``ApplicationInterviewRepository.update_schedule``): the recruiter on
        the invite stays whoever first booked it, even if a different owner
        makes this edit.

        Args:
            session (AsyncSession): Active database async session.
            current_user (UserContextDto): The authenticated caller.
            application_id (int): The application whose meeting to move.
            dto (InterviewScheduleRequestDto): The new slot and interviewer.

        Returns:
            InterviewDto: The updated meeting.

        Raises:
            ValueError: If the application is missing/not owned, no meeting
                is currently booked for its current stage+round, the
                proposed assignee doesn't hold
                ``RECRUITING_INTERVIEW_EVALUATE``, or the Calendar event no
                longer exists (recoverable: cancel here, then re-schedule).
        """
        application, _job = await self.application_access.load_owned_application(
            session, current_user, application_id, for_update=True
        )
        interview = await self.application_interview_repository.get(
            session, application_id, application.stage, application.current_round
        )
        if interview is None:
            raise ValueError("No interview meeting is scheduled for this session.")
        await self.application_access.validate_interview_assignee(
            session, dto.assignee_id
        )
        # Snapshot the pre-edit slot/interviewer before anything below
        # overwrites them, so the activity entry can say what actually
        # changed (see the "from*" fields on the interview_updated details
        # below). The interview entity stores no attendee snapshot itself
        # (see its docstring), so the "from" assignee comes from the
        # assignment row instead, read before `upsert` below overwrites it.
        from_start_at = interview.start_at
        from_end_at = interview.end_at
        existing_assignment = await self.application_assignment_repository.get(
            session, application_id, application.stage, application.current_round
        )
        from_assignee_id = (
            existing_assignment.assignee_id if existing_assignment else None
        )
        start_utc, end_utc = _to_utc(
            dto.date, dto.start_time, dto.duration_minutes, dto.timezone
        )
        attendee_ids = [application.user_id, dto.assignee_id, interview.scheduled_by]
        try:
            meeting = await self.meeting_scheduling_service.update(
                session,
                interview.google_event_id,
                start_utc,
                end_utc,
                attendee_ids,
                calendar_id=self.interview_calendar_id,
            )
        except MeetingGoneError as e:
            self.logger.error(
                "[InterviewSchedulingService] Calendar event %s gone for "
                "application_id=%s: %s",
                interview.google_event_id,
                application_id,
                e,
            )
            raise ValueError(_MEETING_GONE_MESSAGE) from e

        interview = await self.application_interview_repository.update_schedule(
            session,
            interview,
            start_at=start_utc,
            end_at=end_utc,
            meet_link=meeting.get("meet_link") or None,
        )
        await self.application_assignment_repository.upsert(
            session,
            application_id,
            application.stage,
            application.current_round,
            dto.assignee_id,
            current_user.user_id,
        )
        await record_event(
            session,
            subject_type="application",
            subject_id=application_id,
            actor_id=current_user.user_id,
            event_type=RecruitingEvent.INTERVIEW_UPDATED,
            details={
                "stage": application.stage.value,
                "round": application.current_round,
                "assigneeId": dto.assignee_id,
                "startAt": start_utc.isoformat(),
                "endAt": end_utc.isoformat(),
                "timezone": dto.timezone,
                "googleEventId": meeting["google_event_id"],
                "fromStartAt": from_start_at.isoformat(),
                "fromEndAt": from_end_at.isoformat(),
                "fromAssigneeId": from_assignee_id,
            },
        )
        await session.commit()

        assignee = await self.users_repository.get_user_by_user_id(
            session, dto.assignee_id
        )
        scheduler = await self.users_repository.get_user_by_user_id(
            session, interview.scheduled_by
        )
        return self.recruiting_mapper.to_interview_dto(
            interview,
            assignee_id=dto.assignee_id,
            assignee_name=_staff_name(assignee),
            scheduled_by_name=_staff_name(scheduler),
        )

    async def cancel(
        self,
        session: AsyncSession,
        current_user: UserContextDto,
        application_id: int,
    ) -> None:
        """Cancel an application's current stage+round's booked meeting.

        Deletes the Calendar event (Google mails the cancellation) and the
        stored row; the ``interview_cancelled`` activity entry is the only
        remaining record, matching reject/blacklist's tombstone-free
        approach.

        The application's sub_status falls back to ``"scheduling"`` only
        when it is currently ``"scheduled"``. It is deliberately left alone
        when it's ``"evaluated"``: once the interview has happened and been
        graded, tidying up the calendar entry must not silently erase that
        evaluation progress.

        Args:
            session (AsyncSession): Active database async session.
            current_user (UserContextDto): The authenticated caller.
            application_id (int): The application whose meeting to cancel.

        Raises:
            ValueError: If the application is missing/not owned, or no
                meeting is currently booked for its current stage+round.
        """
        application, _job = await self.application_access.load_owned_application(
            session, current_user, application_id, for_update=True
        )
        interview = await self.application_interview_repository.get(
            session, application_id, application.stage, application.current_round
        )
        if interview is None:
            raise ValueError("No interview meeting is scheduled for this session.")
        await self._delete_meeting(
            session, interview, application_id, current_user.user_id
        )
        # Guarded -- unlike schedule()'s unconditional `sub_status =
        # "scheduled"` above. See that comment for the other half of the
        # asymmetry: this only reverts from exactly "scheduled", so
        # cancelling a past, already-graded interview's calendar entry never
        # erases "evaluated".
        if application.sub_status == "scheduled":
            application.sub_status = "scheduling"
            await self.application_repository.update(session, application)
        await session.commit()

    async def cancel_for_round(
        self,
        session: AsyncSession,
        application_id: int,
        stage: ApplicationStage,
        round: int,
        actor_user_id: int,
        *,
        via: str,
    ) -> bool:
        """Cancel one round's still-upcoming meeting, mid-caller-transaction.

        The ghost-meeting cleanup ``BoardService``'s advance/round-advance/
        reject paths drive: the detail page only ever surfaces the meeting on
        the application's CURRENT stage+round, so once a decision moves the
        application on, a meeting left booked on the round behind it is live on
        everyone's calendar and invisible in Purrf.

        Four deliberate differences from ``cancel``, which is the recruiter's
        own explicit "cancel this meeting" action:

        - The stage+round come in as arguments. The caller may already have
          moved the application, so ``application.current_round`` no longer
          points at the round being cleaned up.
        - No ownership check. The caller row-locked the application and gated
          on ownership before deciding; re-checking here would just repeat a
          query, and this method deliberately takes an actor id rather than a
          ``UserContextDto`` to make that non-negotiable.
        - No commit, and no ``sub_status`` write. It runs inside the caller's
          transaction, and the caller overwrites ``sub_status`` immediately
          after (``"pending"``, or ``None`` for a terminal target).
        - A meeting that has already started is left strictly alone. It is
          history rather than a ghost, and deleting its Calendar event would
          mail every attendee a cancellation for something that already
          happened.

        Args:
            session (AsyncSession): The caller's active, uncommitted session.
            application_id (int): The application being decided on.
            stage (ApplicationStage): The stage being left.
            round (int): The round being left, within that stage.
            actor_user_id (int): The recruiter making the decision, recorded
                as the activity entry's actor.
            via (str): Which decision triggered this, recorded as the
                ``interview_cancelled`` entry's ``"via"`` detail so the
                timeline can tell an automatic cleanup apart from a recruiter
                cancelling a meeting on purpose. One of ``"stage_changed"``,
                ``"round_advanced"``, ``"rejected"``.

        Returns:
            bool: True if a meeting was cancelled; False if that round had
                none booked, or the one it had has already started.
        """
        interview = await self.application_interview_repository.get(
            session, application_id, stage, round
        )
        if interview is None:
            return False
        if interview.start_at <= datetime.now(timezone.utc):
            return False
        await self._delete_meeting(
            session,
            interview,
            application_id,
            actor_user_id,
            extra_details={"via": via},
        )
        return True

    async def _delete_meeting(
        self,
        session: AsyncSession,
        interview,
        application_id: int,
        actor_user_id: int,
        extra_details: dict | None = None,
    ) -> None:
        """Drop a meeting's Calendar event, its row, and log the cancellation.

        Shared by ``cancel`` and ``cancel_for_round`` so the Google call, the
        end-state-wins policy on a failed delete, and the activity payload
        exist in exactly one place. Neither the application's ``sub_status``
        nor the commit belongs here — those differ between the two callers.

        A Calendar delete that Google refuses is logged and swallowed: the row
        is removed anyway, because the desired end state is "this meeting is
        gone from Purrf", and blocking on Google would leave the caller's
        decision half-applied.

        Args:
            session (AsyncSession): Active database async session.
            interview (ApplicationInterviewEntity): The row to remove.
            application_id (int): Its owning application.
            actor_user_id (int): Recorded as the activity entry's actor.
            extra_details (dict | None): Extra keys merged into the
                ``interview_cancelled`` details payload.
        """
        # The interview entity stores no attendee snapshot itself (see its
        # docstring); the assignee it was scheduled with comes from the
        # assignment row, read before the row is deleted below.
        assignment = await self.application_assignment_repository.get(
            session, application_id, interview.stage, interview.round
        )
        cancelled_assignee_id = assignment.assignee_id if assignment else None

        _succeeded, failed = await self.meeting_scheduling_service.cancel(
            [interview.google_event_id],
            calendar_id=self.interview_calendar_id,
        )
        if failed:
            self.logger.warning(
                "[InterviewSchedulingService] Failed to delete Calendar "
                "event(s) %s for application_id=%s; removing the local row "
                "anyway (end state is what matters).",
                failed,
                application_id,
            )

        await self.application_interview_repository.delete(session, interview)
        await record_event(
            session,
            subject_type="application",
            subject_id=application_id,
            actor_id=actor_user_id,
            event_type=RecruitingEvent.INTERVIEW_CANCELLED,
            details={
                "stage": interview.stage.value,
                "round": interview.round,
                "assigneeId": cancelled_assignee_id,
                "startAt": interview.start_at.isoformat(),
                "endAt": interview.end_at.isoformat(),
                # No zone key, unlike the scheduled/updated entries above:
                # those record the wall clock the recruiter typed, and a cancel
                # types nothing. The timeline renders these instants in the
                # reader's own zone anyway.
                "googleEventId": interview.google_event_id,
                **(extra_details or {}),
            },
        )
