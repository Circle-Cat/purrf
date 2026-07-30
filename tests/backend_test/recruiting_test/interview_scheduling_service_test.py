import unittest
from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, create_autospec

from backend.common.exceptions import MeetingGoneError
from backend.common.recruiting_enums import ApplicationStage
from backend.dto.interview_dto import InterviewScheduleRequestDto
from backend.dto.user_context_dto import UserContextDto
from backend.entity.application_entity import ApplicationEntity
from backend.recruiting.application_access import ApplicationAccess
from backend.recruiting.interview_scheduling_service import InterviewSchedulingService
from backend.recruiting.recruiting_mapper import RecruitingMapper
from backend.repository.application_activity_repository import (
    ApplicationActivityRepository,
)
from backend.repository.application_assignment_repository import (
    ApplicationAssignmentRepository,
)
from backend.repository.application_interview_repository import (
    ApplicationInterviewRepository,
)

CANDIDATE_ID = 3
ASSIGNEE_ID = 42
OWNER_ID = 2
APPLICATION_ID = 10
JOB_ID = 1


class _BaseTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.session = AsyncMock()

        # autospec (not a bare MagicMock) so a caller/repo signature drift
        # (e.g. a new required param) fails the test instead of silently
        # accepting any arity -- same convention board_service_test.py uses.
        self.application_access = create_autospec(ApplicationAccess, instance=True)
        self.assignment_repo = create_autospec(
            ApplicationAssignmentRepository, instance=True
        )
        self.interview_repo = create_autospec(
            ApplicationInterviewRepository, instance=True
        )
        self.activity_repo = create_autospec(
            ApplicationActivityRepository, instance=True
        )
        self.application_repo = MagicMock()
        self.application_repo.update = AsyncMock(
            side_effect=lambda session, entity: entity
        )
        self.users_repo = MagicMock()
        self.user_emails_repo = MagicMock()
        self.user_emails_repo.get_contact_emails_by_user_ids = AsyncMock(
            return_value={CANDIDATE_ID: "cand@example.com"}
        )
        self.meeting_svc = AsyncMock()
        self.meeting_svc.schedule = AsyncMock(return_value=self._meeting_result())
        self.meeting_svc.update = AsyncMock(return_value=self._meeting_result())
        self.meeting_svc.cancel = AsyncMock(return_value=(["evt-1"], []))
        self.logger = MagicMock()
        self.mapper = RecruitingMapper()

        self.application = self._application()
        self.job = SimpleNamespace(job_id=JOB_ID)
        self.application_access.load_owned_application = AsyncMock(
            return_value=(self.application, self.job)
        )
        self.application_access.validate_interview_assignee = AsyncMock(
            return_value=None
        )
        self.interview_repo.get = AsyncMock(return_value=None)
        self.interview_repo.create = AsyncMock(side_effect=self._create_interview)
        self.interview_repo.update_schedule = AsyncMock(
            side_effect=self._update_interview_schedule
        )
        self.interview_repo.delete = AsyncMock()
        # The "existing assignment" update()/cancel() read before overwriting/
        # deleting -- default matches _interview_row()'s implied assignee so
        # a test that doesn't care about the "from" assignee still gets a
        # real int rather than an unconfigured autospec MagicMock.
        self.assignment_repo.get = AsyncMock(
            return_value=self._assignment_row(assignee_id=ASSIGNEE_ID)
        )

        self.service = InterviewSchedulingService(
            self.logger,
            self.application_access,
            self.application_repo,
            self.assignment_repo,
            self.interview_repo,
            self.activity_repo,
            self.users_repo,
            self.user_emails_repo,
            self.meeting_svc,
            self.mapper,
        )

        # Candidate/interviewer/recruiter are ALL fetched through
        # get_user_by_user_id -- a single return_value would let the
        # recruiter silently inherit the candidate's name, so this is
        # keyed by id (mirrors board_service_test.py's `_users_by_id`).
        self._users_by_id({
            CANDIDATE_ID: SimpleNamespace(first_name="Ana", last_name="Lopez"),
            ASSIGNEE_ID: SimpleNamespace(first_name="Ivy", last_name="Interviewer"),
            OWNER_ID: SimpleNamespace(first_name="Rae", last_name="Recruiter"),
        })

    def _users_by_id(self, rows):
        async def lookup(_session, user_id):
            return rows.get(user_id)

        self.users_repo.get_user_by_user_id = AsyncMock(side_effect=lookup)

    def _application(
        self,
        stage=ApplicationStage.BEHAVIORAL,
        round=1,
        sub_status="scheduling",
    ):
        app = ApplicationEntity(
            job_id=JOB_ID,
            user_id=CANDIDATE_ID,
            stage=stage,
            sub_status=sub_status,
            current_round=round,
        )
        app.application_id = APPLICATION_ID
        return app

    def _ctx(self, user_id=OWNER_ID):
        return UserContextDto(sub="s", primary_email="hr@x.com", user_id=user_id)

    def _dto(
        self,
        assignee_id=ASSIGNEE_ID,
        day=date(2026, 8, 5),
        start_time="14:00",
        duration_minutes=45,
        timezone_name="America/Los_Angeles",
    ):
        return InterviewScheduleRequestDto(
            assignee_id=assignee_id,
            date=day,
            start_time=start_time,
            duration_minutes=duration_minutes,
            timezone=timezone_name,
        )

    def _meeting_result(self, event_id="evt-1", meet_link="https://meet.example/abc"):
        return {
            "google_event_id": event_id,
            "meet_link": meet_link,
            "entry_points": [],
            "conference_id": "conf-1",
            "created": "2026-08-01T00:00:00Z",
        }

    def _assignment_row(self, **overrides):
        base = dict(
            application_id=APPLICATION_ID,
            stage=ApplicationStage.BEHAVIORAL,
            round=1,
            assignee_id=ASSIGNEE_ID,
            assigned_by=OWNER_ID,
        )
        base.update(overrides)
        return SimpleNamespace(**base)

    def _interview_row(self, **overrides):
        base = dict(
            interview_id=99,
            application_id=APPLICATION_ID,
            stage=ApplicationStage.BEHAVIORAL,
            round=1,
            google_event_id="evt-1",
            meet_link="https://meet.example/abc",
            start_at=datetime(2026, 8, 5, 21, 0, tzinfo=timezone.utc),
            end_at=datetime(2026, 8, 5, 21, 45, tzinfo=timezone.utc),
            scheduled_by=OWNER_ID,
        )
        base.update(overrides)
        return SimpleNamespace(**base)

    async def _create_interview(self, session, **kwargs):
        return SimpleNamespace(interview_id=99, **kwargs)

    async def _update_interview_schedule(self, session, entity, **kwargs):
        for key, value in kwargs.items():
            setattr(entity, key, value)
        return entity


# -- schedule: happy path --


class ScheduleTest(_BaseTest):
    async def test_converts_wall_clock_to_utc(self):
        # 2:00 PM America/Los_Angeles on 2026-08-05 is PDT (UTC-7) => 21:00Z
        await self.service.schedule(
            self.session, self._ctx(), APPLICATION_ID, self._dto()
        )
        _session, _summary, passed_start, passed_end, _attendees = (
            self.meeting_svc.schedule.call_args.args
        )
        self.assertEqual(passed_start, datetime(2026, 8, 5, 21, 0, tzinfo=timezone.utc))
        self.assertEqual(passed_end, datetime(2026, 8, 5, 21, 45, tzinfo=timezone.utc))

    async def test_converts_wall_clock_across_the_dst_boundary(self):
        # 2026-11-05 is PST (UTC-8) => 2:00 PM local is 22:00Z, not 21:00Z.
        # A naive "always -7" would put this meeting an hour off.
        dto = self._dto(day=date(2026, 11, 5))
        await self.service.schedule(self.session, self._ctx(), APPLICATION_ID, dto)
        _session, _summary, passed_start, passed_end, _attendees = (
            self.meeting_svc.schedule.call_args.args
        )
        self.assertEqual(
            passed_start, datetime(2026, 11, 5, 22, 0, tzinfo=timezone.utc)
        )
        self.assertEqual(passed_end, datetime(2026, 11, 5, 22, 45, tzinfo=timezone.utc))

    async def test_builds_the_meeting_title_from_first_name_and_stage(self):
        await self.service.schedule(
            self.session, self._ctx(), APPLICATION_ID, self._dto()
        )
        passed_summary = self.meeting_svc.schedule.call_args.args[1]
        self.assertEqual(passed_summary, "Ana/Circle Cat, Behavioral")

    async def test_title_has_no_round_suffix_on_a_later_round(self):
        self.application.current_round = 2
        await self.service.schedule(
            self.session, self._ctx(), APPLICATION_ID, self._dto()
        )
        passed_summary = self.meeting_svc.schedule.call_args.args[1]
        self.assertEqual(passed_summary, "Ana/Circle Cat, Behavioral")

    async def test_tech_stage_title_says_technical(self):
        self.application.stage = ApplicationStage.TECH
        await self.service.schedule(
            self.session, self._ctx(), APPLICATION_ID, self._dto()
        )
        passed_summary = self.meeting_svc.schedule.call_args.args[1]
        self.assertEqual(passed_summary, "Ana/Circle Cat, Technical")

    async def test_invites_candidate_interviewer_and_the_acting_recruiter(self):
        await self.service.schedule(
            self.session, self._ctx(user_id=OWNER_ID), APPLICATION_ID, self._dto()
        )
        passed_attendee_ids = self.meeting_svc.schedule.call_args.args[4]
        self.assertEqual(passed_attendee_ids, [CANDIDATE_ID, ASSIGNEE_ID, OWNER_ID])

    async def test_persists_the_row_and_marks_the_application_scheduled(self):
        result = await self.service.schedule(
            self.session, self._ctx(user_id=OWNER_ID), APPLICATION_ID, self._dto()
        )
        self.interview_repo.create.assert_awaited_once()
        kwargs = self.interview_repo.create.call_args.kwargs
        self.assertEqual(kwargs["application_id"], APPLICATION_ID)
        self.assertEqual(kwargs["stage"], ApplicationStage.BEHAVIORAL)
        self.assertEqual(kwargs["round"], 1)
        self.assertEqual(kwargs["google_event_id"], "evt-1")
        self.assertEqual(kwargs["meet_link"], "https://meet.example/abc")
        # The recruiter's picked zone is an INPUT only -- it converts the wall
        # clock to UTC and is never persisted, because every surface renders
        # these instants in the viewer's own zone instead.
        self.assertNotIn("timezone", kwargs)
        self.assertEqual(kwargs["scheduled_by"], OWNER_ID)
        self.assertEqual(self.application.sub_status, "scheduled")
        self.application_repo.update.assert_awaited_once_with(
            self.session, self.application
        )
        self.session.commit.assert_awaited_once()
        self.assertEqual(result.interview_id, 99)
        self.assertEqual(result.assignee_id, ASSIGNEE_ID)
        self.assertEqual(result.assignee_name, "Ivy Interviewer")
        self.assertEqual(result.scheduled_by_name, "Rae Recruiter")

    async def test_writes_an_interview_scheduled_activity_entry(self):
        await self.service.schedule(
            self.session, self._ctx(user_id=OWNER_ID), APPLICATION_ID, self._dto()
        )
        self.activity_repo.create.assert_awaited_once()
        args, kwargs = self.activity_repo.create.call_args
        self.assertEqual(args[:3], (self.session, APPLICATION_ID, OWNER_ID))
        self.assertEqual(args[3], "interview_scheduled")
        self.assertEqual(kwargs["details"]["assigneeId"], ASSIGNEE_ID)

    async def test_interview_scheduled_activity_carries_the_full_detail_set(self):
        # The timeline needs the zone and the calendar event id (not just the
        # UTC instant) to render "Scheduled the Behavioral interview meeting
        # for 2026-08-05 14:00 America/Los_Angeles with <name>" without
        # guessing -- see get_application_activity's _ASSIGNEE_NAME_FIELDS
        # entry, which resolves assigneeId -> assigneeName from this same dict.
        await self.service.schedule(
            self.session, self._ctx(user_id=OWNER_ID), APPLICATION_ID, self._dto()
        )
        _args, kwargs = self.activity_repo.create.call_args
        self.assertEqual(
            kwargs["details"],
            {
                "stage": "behavioral",
                "round": 1,
                "assigneeId": ASSIGNEE_ID,
                "startAt": "2026-08-05T21:00:00+00:00",
                "endAt": "2026-08-05T21:45:00+00:00",
                "timezone": "America/Los_Angeles",
                "googleEventId": "evt-1",
            },
        )

    async def test_overwrites_the_rounds_assignment(self):
        await self.service.schedule(
            self.session, self._ctx(user_id=OWNER_ID), APPLICATION_ID, self._dto()
        )
        self.assignment_repo.upsert.assert_awaited_once_with(
            self.session,
            APPLICATION_ID,
            ApplicationStage.BEHAVIORAL,
            1,
            ASSIGNEE_ID,
            OWNER_ID,
        )

    async def test_requests_owner_only_access_not_assignee_or_read_all(self):
        # Booking a meeting is a job-ownership decision, not something a
        # mere assignee or a read.all holder may do -- assert exactly which
        # access flags this service asks ApplicationAccess for, so a
        # regression here (e.g. `allow_assignee=True`) is caught even though
        # every other test mocks load_owned_application to always succeed.
        ctx = self._ctx(user_id=OWNER_ID)
        await self.service.schedule(self.session, ctx, APPLICATION_ID, self._dto())
        self.application_access.load_owned_application.assert_awaited_once_with(
            self.session, ctx, APPLICATION_ID, for_update=True
        )


# -- schedule: rejection paths --


class ScheduleRejectionTest(_BaseTest):
    async def test_a_non_owner_gets_the_collapsed_not_found_error(self):
        self.application_access.load_owned_application = AsyncMock(
            side_effect=ValueError(f"application {APPLICATION_ID} not found")
        )
        with self.assertRaises(ValueError) as ctx:
            await self.service.schedule(
                self.session, self._ctx(user_id=999), APPLICATION_ID, self._dto()
            )
        self.assertEqual(str(ctx.exception), f"application {APPLICATION_ID} not found")
        self.meeting_svc.schedule.assert_not_awaited()

    async def test_a_non_interview_stage_is_rejected(self):
        self.application.stage = ApplicationStage.RECRUITER_SCREENING
        with self.assertRaises(ValueError):
            await self.service.schedule(
                self.session, self._ctx(), APPLICATION_ID, self._dto()
            )
        self.meeting_svc.schedule.assert_not_awaited()
        self.assignment_repo.upsert.assert_not_awaited()

    async def test_a_terminal_stage_is_rejected(self):
        self.application.stage = ApplicationStage.REJECTED
        with self.assertRaises(ValueError):
            await self.service.schedule(
                self.session, self._ctx(), APPLICATION_ID, self._dto()
            )
        self.meeting_svc.schedule.assert_not_awaited()

    async def test_an_already_booked_round_is_rejected(self):
        self.interview_repo.get = AsyncMock(return_value=self._interview_row())
        with self.assertRaises(ValueError):
            await self.service.schedule(
                self.session, self._ctx(), APPLICATION_ID, self._dto()
            )
        self.meeting_svc.schedule.assert_not_awaited()
        self.assignment_repo.upsert.assert_not_awaited()

    async def test_an_assignee_without_the_evaluate_permission_is_rejected(self):
        self.application_access.validate_interview_assignee = AsyncMock(
            side_effect=ValueError(
                f"assignee {ASSIGNEE_ID} is not an active interview evaluator"
            )
        )
        with self.assertRaises(ValueError):
            await self.service.schedule(
                self.session, self._ctx(), APPLICATION_ID, self._dto()
            )
        self.meeting_svc.schedule.assert_not_awaited()
        self.assignment_repo.upsert.assert_not_awaited()

    async def test_a_candidate_with_no_email_is_rejected(self):
        self.user_emails_repo.get_contact_emails_by_user_ids = AsyncMock(
            return_value={}
        )
        with self.assertRaises(ValueError):
            await self.service.schedule(
                self.session, self._ctx(), APPLICATION_ID, self._dto()
            )
        self.meeting_svc.schedule.assert_not_awaited()
        self.assignment_repo.upsert.assert_not_awaited()

    async def test_nothing_is_written_when_google_fails(self):
        self.meeting_svc.schedule = AsyncMock(side_effect=RuntimeError("boom"))
        with self.assertRaises(RuntimeError):
            await self.service.schedule(
                self.session, self._ctx(), APPLICATION_ID, self._dto()
            )
        self.interview_repo.create.assert_not_awaited()
        self.assertEqual(self.application.sub_status, "scheduling")
        self.application_repo.update.assert_not_awaited()
        self.session.commit.assert_not_awaited()


# -- update --


class UpdateTest(_BaseTest):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.existing = self._interview_row()
        self.interview_repo.get = AsyncMock(return_value=self.existing)

    async def test_moves_the_time_and_keeps_scheduled_by(self):
        # A different caller than the original scheduler (OWNER_ID) makes
        # the edit; `scheduled_by` on the invite must not change.
        dto = self._dto(day=date(2026, 8, 6), start_time="15:00")
        result = await self.service.update(
            self.session, self._ctx(user_id=999), APPLICATION_ID, dto
        )
        self.meeting_svc.update.assert_awaited_once()
        args = self.meeting_svc.update.call_args.args
        self.assertEqual(args[0], self.session)
        self.assertEqual(args[1], "evt-1")
        self.assertEqual(args[2], datetime(2026, 8, 6, 22, 0, tzinfo=timezone.utc))
        self.assertEqual(args[3], datetime(2026, 8, 6, 22, 45, tzinfo=timezone.utc))
        self.assertEqual(self.existing.scheduled_by, OWNER_ID)
        self.assertEqual(result.scheduled_by_name, "Rae Recruiter")

    async def test_swaps_the_interviewer_and_overwrites_the_assignment(self):
        new_assignee = 55
        self._users_by_id({
            CANDIDATE_ID: SimpleNamespace(first_name="Ana", last_name="Lopez"),
            ASSIGNEE_ID: SimpleNamespace(first_name="Ivy", last_name="Interviewer"),
            OWNER_ID: SimpleNamespace(first_name="Rae", last_name="Recruiter"),
            new_assignee: SimpleNamespace(first_name="Sam", last_name="Sub"),
        })
        dto = self._dto(assignee_id=new_assignee)
        result = await self.service.update(
            self.session, self._ctx(user_id=OWNER_ID), APPLICATION_ID, dto
        )
        self.assignment_repo.upsert.assert_awaited_once_with(
            self.session,
            APPLICATION_ID,
            ApplicationStage.BEHAVIORAL,
            1,
            new_assignee,
            OWNER_ID,
        )
        self.assertEqual(result.assignee_id, new_assignee)
        self.assertEqual(result.assignee_name, "Sam Sub")

    async def test_patches_a_past_meeting_too(self):
        # No past/future branch: the invariant "assignment and calendar never
        # diverge" is worth more than avoiding an odd notification.
        self.existing.start_at = datetime(2020, 1, 1, tzinfo=timezone.utc)
        dto = self._dto(day=date(2026, 8, 6))
        await self.service.update(self.session, self._ctx(), APPLICATION_ID, dto)
        self.meeting_svc.update.assert_awaited_once()

    async def test_a_gone_calendar_event_surfaces_a_recoverable_message(self):
        self.meeting_svc.update = AsyncMock(side_effect=MeetingGoneError("gone"))
        with self.assertRaises(ValueError) as ctx:
            await self.service.update(
                self.session, self._ctx(), APPLICATION_ID, self._dto()
            )
        self.assertIn("no longer exists on the calendar", str(ctx.exception))

    async def test_a_gone_calendar_event_leaves_the_row_unchanged(self):
        # A DTO with a DIFFERENT slot than `_interview_row()`'s default, so a
        # reordering bug (writing the row before the Google call) can't hide
        # behind "the new value happens to equal the old one".
        original_start = self.existing.start_at
        original_meet_link = self.existing.meet_link
        dto = self._dto(day=date(2026, 8, 6), start_time="09:00")
        self.meeting_svc.update = AsyncMock(side_effect=MeetingGoneError("gone"))
        with self.assertRaises(ValueError):
            await self.service.update(self.session, self._ctx(), APPLICATION_ID, dto)
        self.interview_repo.update_schedule.assert_not_awaited()
        self.assertEqual(self.existing.start_at, original_start)
        self.assertEqual(self.existing.meet_link, original_meet_link)
        self.assignment_repo.upsert.assert_not_awaited()
        self.session.commit.assert_not_awaited()

    async def test_writes_an_interview_updated_activity_entry(self):
        await self.service.update(
            self.session, self._ctx(user_id=OWNER_ID), APPLICATION_ID, self._dto()
        )
        self.activity_repo.create.assert_awaited_once()
        args, _kwargs = self.activity_repo.create.call_args
        self.assertEqual(args[3], "interview_updated")

    async def test_interview_updated_activity_carries_the_full_detail_set_incl_from_fields(
        self,
    ):
        # The "from*" trio lets the timeline say what actually changed (time
        # moved, interviewer swapped, or both) -- see the `fromAssigneeId` ->
        # `fromAssigneeName` entry in get_application_activity's
        # _ASSIGNEE_NAME_FIELDS, which resolves it from this same dict.
        new_assignee = 55
        self._users_by_id({
            CANDIDATE_ID: SimpleNamespace(first_name="Ana", last_name="Lopez"),
            ASSIGNEE_ID: SimpleNamespace(first_name="Ivy", last_name="Interviewer"),
            OWNER_ID: SimpleNamespace(first_name="Rae", last_name="Recruiter"),
            new_assignee: SimpleNamespace(first_name="Sam", last_name="Sub"),
        })
        dto = self._dto(
            assignee_id=new_assignee, day=date(2026, 8, 6), start_time="15:00"
        )
        await self.service.update(
            self.session, self._ctx(user_id=OWNER_ID), APPLICATION_ID, dto
        )
        _args, kwargs = self.activity_repo.create.call_args
        self.assertEqual(
            kwargs["details"],
            {
                "stage": "behavioral",
                "round": 1,
                "assigneeId": new_assignee,
                "startAt": "2026-08-06T22:00:00+00:00",
                "endAt": "2026-08-06T22:45:00+00:00",
                "timezone": "America/Los_Angeles",
                "googleEventId": "evt-1",
                "fromStartAt": "2026-08-05T21:00:00+00:00",
                "fromEndAt": "2026-08-05T21:45:00+00:00",
                "fromAssigneeId": ASSIGNEE_ID,
            },
        )

    async def test_interview_updated_from_assignee_is_none_when_no_assignment_row_exists(
        self,
    ):
        self.assignment_repo.get = AsyncMock(return_value=None)
        await self.service.update(
            self.session, self._ctx(user_id=OWNER_ID), APPLICATION_ID, self._dto()
        )
        _args, kwargs = self.activity_repo.create.call_args
        self.assertIsNone(kwargs["details"]["fromAssigneeId"])

    async def test_no_booking_yet_is_rejected(self):
        self.interview_repo.get = AsyncMock(return_value=None)
        with self.assertRaises(ValueError):
            await self.service.update(
                self.session, self._ctx(), APPLICATION_ID, self._dto()
            )
        self.meeting_svc.update.assert_not_awaited()

    async def test_requests_owner_only_access_not_assignee_or_read_all(self):
        # Same access-flag guard as schedule's: rescheduling/reassigning a
        # meeting is an owner decision, not something a mere assignee or a
        # read.all holder may do.
        ctx = self._ctx(user_id=OWNER_ID)
        await self.service.update(self.session, ctx, APPLICATION_ID, self._dto())
        self.application_access.load_owned_application.assert_awaited_once_with(
            self.session, ctx, APPLICATION_ID, for_update=True
        )


# -- cancel --


class CancelTest(_BaseTest):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.existing = self._interview_row()
        self.interview_repo.get = AsyncMock(return_value=self.existing)

    async def test_deletes_the_row_and_writes_an_activity_entry(self):
        await self.service.cancel(
            self.session, self._ctx(user_id=OWNER_ID), APPLICATION_ID
        )
        self.interview_repo.delete.assert_awaited_once_with(self.session, self.existing)
        self.activity_repo.create.assert_awaited_once()
        args, _kwargs = self.activity_repo.create.call_args
        self.assertEqual(args[3], "interview_cancelled")
        self.meeting_svc.cancel.assert_awaited_once_with(["evt-1"])
        self.session.commit.assert_awaited_once()

    async def test_interview_cancelled_activity_carries_the_full_detail_set(self):
        # Unlike schedule/update, this used to write only {stage, round}: the
        # timeline needs what was cancelled (who, when) to say "Cancelled the
        # Behavioral interview meeting that was set for ..." -- read from the
        # interview row (start/end/event id) and the assignment row (assignee,
        # since the interview entity itself stores no attendee snapshot), both
        # BEFORE the row is deleted.
        #
        # No zone key, unlike schedule/update: those record the wall clock the
        # recruiter typed, and a cancel types nothing. The timeline renders
        # these instants in the reader's own zone.
        await self.service.cancel(
            self.session, self._ctx(user_id=OWNER_ID), APPLICATION_ID
        )
        _args, kwargs = self.activity_repo.create.call_args
        self.assertEqual(
            kwargs["details"],
            {
                "stage": "behavioral",
                "round": 1,
                "assigneeId": ASSIGNEE_ID,
                "startAt": "2026-08-05T21:00:00+00:00",
                "endAt": "2026-08-05T21:45:00+00:00",
                "googleEventId": "evt-1",
            },
        )

    async def test_interview_cancelled_assignee_is_none_when_no_assignment_row_exists(
        self,
    ):
        self.assignment_repo.get = AsyncMock(return_value=None)
        await self.service.cancel(
            self.session, self._ctx(user_id=OWNER_ID), APPLICATION_ID
        )
        _args, kwargs = self.activity_repo.create.call_args
        self.assertIsNone(kwargs["details"]["assigneeId"])

    async def test_scheduled_sub_status_falls_back_to_scheduling(self):
        self.application.sub_status = "scheduled"
        await self.service.cancel(self.session, self._ctx(), APPLICATION_ID)
        self.assertEqual(self.application.sub_status, "scheduling")
        self.application_repo.update.assert_awaited_once_with(
            self.session, self.application
        )

    async def test_evaluated_sub_status_is_left_alone(self):
        # Mutation check: delete the `== "scheduled"` guard in the service
        # and THIS test must go red. Without the guard, tidying up a
        # finished interview's calendar entry would erase the evaluation
        # progress.
        self.application.sub_status = "evaluated"
        await self.service.cancel(self.session, self._ctx(), APPLICATION_ID)
        self.assertEqual(self.application.sub_status, "evaluated")
        self.application_repo.update.assert_not_awaited()

    async def test_no_booking_yet_is_rejected(self):
        self.interview_repo.get = AsyncMock(return_value=None)
        with self.assertRaises(ValueError):
            await self.service.cancel(self.session, self._ctx(), APPLICATION_ID)
        self.meeting_svc.cancel.assert_not_awaited()

    async def test_requests_owner_only_access_not_assignee_or_read_all(self):
        # Same access-flag guard as schedule's/update's: cancelling a
        # meeting is an owner decision, not something a mere assignee or a
        # read.all holder may do.
        ctx = self._ctx(user_id=OWNER_ID)
        await self.service.cancel(self.session, ctx, APPLICATION_ID)
        self.application_access.load_owned_application.assert_awaited_once_with(
            self.session, ctx, APPLICATION_ID, for_update=True
        )


if __name__ == "__main__":
    unittest.main()
