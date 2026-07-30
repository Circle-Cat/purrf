"""Recruiting interview-meeting scheduling (thin domain controller).

Owns the recruiting rules — who may book, which stages can be booked, which
assignment row the meeting belongs to, what the application's sub_status
becomes — and delegates every Google call to the shared
``MeetingSchedulingService``.
"""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.exceptions import MeetingGoneError
from backend.common.recruiting_enums import ApplicationStage
from backend.dto.interview_dto import InterviewDto, InterviewScheduleRequestDto
from backend.dto.user_context_dto import UserContextDto

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


def _full_name(user) -> str | None:
    if user is None:
        return None
    return f"{user.first_name} {user.last_name}".strip()


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
        application_activity_repository,
        users_repository,
        user_emails_repository,
        meeting_scheduling_service,
        recruiting_mapper,
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
            application_activity_repository (ApplicationActivityRepository):
                Append-only audit log, written on schedule/update/cancel.
            users_repository (UsersRepository): Candidate/interviewer/
                recruiter name resolution for the meeting title and the
                response DTO.
            user_emails_repository (UserEmailsRepository): Candidate
                contact-email presence check (a hard reject when missing).
            meeting_scheduling_service (MeetingSchedulingService): The
                domain-agnostic Google Calendar/Meet transport.
            recruiting_mapper (RecruitingMapper): Entity->DTO conversion.
        """
        self.logger = logger
        self.application_access = application_access
        self.application_repository = application_repository
        self.application_assignment_repository = application_assignment_repository
        self.application_interview_repository = application_interview_repository
        self.application_activity_repository = application_activity_repository
        self.users_repository = users_repository
        self.user_emails_repository = user_emails_repository
        self.meeting_scheduling_service = meeting_scheduling_service
        self.recruiting_mapper = recruiting_mapper

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
            raise ValueError("This round already has an interview meeting scheduled.")
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
                session, summary, start_utc, end_utc, attendee_ids
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
            timezone=dto.timezone,
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
        await self.application_activity_repository.create(
            session,
            application_id,
            current_user.user_id,
            "interview_scheduled",
            details={
                "stage": application.stage.value,
                "round": application.current_round,
                "assigneeId": dto.assignee_id,
                "startAt": start_utc.isoformat(),
                "endAt": end_utc.isoformat(),
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
            assignee_name=_full_name(assignee),
            scheduled_by_name=_full_name(scheduler),
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
            raise ValueError("No interview meeting is scheduled for this round.")
        await self.application_access.validate_interview_assignee(
            session, dto.assignee_id
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
            timezone=dto.timezone,
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
        await self.application_activity_repository.create(
            session,
            application_id,
            current_user.user_id,
            "interview_updated",
            details={
                "stage": application.stage.value,
                "round": application.current_round,
                "assigneeId": dto.assignee_id,
                "startAt": start_utc.isoformat(),
                "endAt": end_utc.isoformat(),
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
            assignee_name=_full_name(assignee),
            scheduled_by_name=_full_name(scheduler),
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
            raise ValueError("No interview meeting is scheduled for this round.")

        _succeeded, failed = await self.meeting_scheduling_service.cancel([
            interview.google_event_id
        ])
        if failed:
            self.logger.warning(
                "[InterviewSchedulingService] Failed to delete Calendar "
                "event(s) %s for application_id=%s; removing the local row "
                "anyway (end state is what matters).",
                failed,
                application_id,
            )

        await self.application_interview_repository.delete(session, interview)
        # Guarded -- unlike schedule()'s unconditional `sub_status =
        # "scheduled"` above. See that comment for the other half of the
        # asymmetry: this only reverts from exactly "scheduled", so
        # cancelling a past, already-graded interview's calendar entry never
        # erases "evaluated".
        if application.sub_status == "scheduled":
            application.sub_status = "scheduling"
            await self.application_repository.update(session, application)
        await self.application_activity_repository.create(
            session,
            application_id,
            current_user.user_id,
            "interview_cancelled",
            details={
                "stage": application.stage.value,
                "round": application.current_round,
            },
        )
        await session.commit()
