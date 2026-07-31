import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, AsyncMock

from backend.mentorship.meeting_service import MeetingService
from backend.dto.user_context_dto import UserContextDto
from backend.dto.meeting_dto import MeetingDto
from backend.dto.meeting_create_dto import MeetingCreateDto
from backend.dto.google_meeting_response_detail_dto import (
    GoogleMeetingResponseDetailDto,
)
from backend.entity.users_entity import UsersEntity
from backend.entity.mentorship_pairs_entity import MentorshipPairsEntity
from backend.common.mentorship_enums import PairStatus
from backend.common.permissions import Permission


class TestMeetingServiceV1(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.mock_logger = MagicMock()
        self.mock_pairs_repo = MagicMock()
        self.mock_pairs_repo.get_pairs_by_user_and_round = AsyncMock()
        self.mock_pairs_repo.get_pair_by_mentee_and_round = AsyncMock()
        self.mock_pairs_repo.upsert_pairs = AsyncMock()

        self.mock_mapper = MagicMock()
        self.mock_users_repo = MagicMock()
        self.mock_users_repo.get_user_by_user_id = AsyncMock()
        self.mock_session = AsyncMock()

        self.mock_meeting_scheduling_service = AsyncMock()
        self.meeting_service = MeetingService(
            logger=self.mock_logger,
            mentorship_pairs_repository=self.mock_pairs_repo,
            mentorship_mapper=self.mock_mapper,
            users_repository=self.mock_users_repo,
            meeting_scheduling_service=self.mock_meeting_scheduling_service,
            mentorship_calendar_id="cal-mentorship",
        )

        self.user_id = 1
        self.round_id = 10
        self.partner_id = 100
        self.user_context = MagicMock(
            spec=UserContextDto,
            sub="sub-123",
            user_id=self.user_id,
            identity_type="external",
        )
        self.mock_current_user = MagicMock(spec=UsersEntity, user_id=self.user_id)
        self.mock_current_user.timezone = "America/New_York"
        self.mock_users_repo.get_user_by_user_id.return_value = self.mock_current_user

        self.mock_pair_entity = MagicMock(
            spec=MentorshipPairsEntity,
            mentor_id=self.partner_id,
            mentee_id=self.user_id,
            completed_count=3,
            meeting_log={
                "meeting_time_list": [
                    {
                        "meeting_id": "m-1",
                        "start_datetime": "2025-10-01T10:00:00Z",
                        "end_datetime": "2025-10-01T11:00:00Z",
                        "is_completed": True,
                        "created_datetime": "2025-09-30T09:00:00Z",
                    }
                ],
            },
        )

    async def test_get_meetings_by_user_and_round_success(self):
        """Test retrieved and mapped meeting logs for a matched user correctly."""
        self.mock_pairs_repo.get_pairs_by_user_and_round.return_value = [
            self.mock_pair_entity
        ]
        stub_dto = MagicMock(spec=MeetingDto)
        self.mock_mapper.map_to_meeting_dto.return_value = stub_dto

        result = await self.meeting_service.get_meetings_by_user_and_round(
            self.mock_session, self.user_context, self.round_id
        )

        self.assertEqual(result, stub_dto)
        self.mock_pairs_repo.get_pairs_by_user_and_round.assert_awaited_once_with(
            session=self.mock_session, user_id=self.user_id, round_id=self.round_id
        )
        self.mock_mapper.map_to_meeting_dto.assert_called_once_with(
            round_id=self.round_id,
            user_timezone=self.mock_current_user.timezone,
            grouped_pairs=[(self.mock_pair_entity, self.partner_id)],
        )

    async def test_get_meetings_by_user_and_round_no_pair_found(self):
        """Verify that an empty MeetingDto is returned when no mentorship pairs exist."""
        self.mock_pairs_repo.get_pairs_by_user_and_round.return_value = []

        result = await self.meeting_service.get_meetings_by_user_and_round(
            self.mock_session, self.user_context, self.round_id
        )

        self.assertIsInstance(result, MeetingDto)
        self.assertEqual(result.round_id, self.round_id)
        self.assertEqual(result.user_timezone, "America/New_York")
        self.assertEqual(len(result.meeting_info), 0)

        self.mock_mapper.map_to_meeting_dto.assert_not_called()

    async def test_upsert_meetings_success(self):
        """Test new meeting slots are successfully validated and persisted."""
        self.mock_pairs_repo.get_pair_by_mentee_and_round.return_value = (
            self.mock_pair_entity
        )
        self.mock_pairs_repo.upsert_pairs.return_value = self.mock_pair_entity

        payload = MeetingCreateDto(
            round_id=self.round_id,
            start_datetime=datetime(2025, 10, 1, 14, 0, tzinfo=timezone.utc),
            end_datetime=datetime(2025, 10, 1, 15, 0, tzinfo=timezone.utc),
            is_completed=True,
        )

        await self.meeting_service.upsert_meetings(
            self.mock_session, self.user_context, payload
        )

        self.mock_pairs_repo.upsert_pairs.assert_awaited_once()
        self.mock_session.commit.assert_awaited_once()

        meeting_list = self.mock_pair_entity.meeting_log["meeting_time_list"]
        self.assertEqual(len(meeting_list), 2)

        new_meeting = meeting_list[-1]

        self.assertIn("created_datetime", new_meeting)
        self.assertIsInstance(new_meeting["created_datetime"], str)
        self.assertTrue(new_meeting["created_datetime"].endswith("Z"))
        self.assertTrue(len(new_meeting["created_datetime"]) > 0)

        self.assertEqual(self.mock_pair_entity.completed_count, 2)

    async def test_upsert_meetings_conflict(self):
        """Test overlapping meeting times trigger a validation error."""
        self.mock_pairs_repo.get_pair_by_mentee_and_round.return_value = (
            self.mock_pair_entity
        )
        payload = MeetingCreateDto(
            round_id=self.round_id,
            start_datetime=datetime(2025, 10, 1, 10, 30, tzinfo=timezone.utc),
            end_datetime=datetime(2025, 10, 1, 11, 30, tzinfo=timezone.utc),
            is_completed=True,
        )

        with self.assertRaisesRegex(ValueError, "This time slot already exists."):
            await self.meeting_service.upsert_meetings(
                self.mock_session, self.user_context, payload
            )

        self.mock_pairs_repo.upsert_pairs.assert_not_awaited()
        self.mock_session.commit.assert_not_awaited()

    async def test_upsert_meetings_preserves_other_keys(self):
        """The write must merge into meeting_log, not replace it wholesale."""
        self.mock_pair_entity.meeting_log = {
            "meeting_time_list": [],
            "google_meetings": [
                {
                    "meeting_id": "evt-1",
                    "start_datetime": "2025-09-01T10:00:00Z",
                    "end_datetime": "2025-09-01T11:00:00Z",
                    "is_completed": True,
                    "created_datetime": "2025-08-01T00:00:00Z",
                }
            ],
        }
        self.mock_pairs_repo.get_pair_by_mentee_and_round.return_value = (
            self.mock_pair_entity
        )
        self.mock_pairs_repo.upsert_pairs.return_value = self.mock_pair_entity

        payload = MeetingCreateDto(
            round_id=self.round_id,
            start_datetime=datetime(2025, 10, 2, 14, 0, tzinfo=timezone.utc),
            end_datetime=datetime(2025, 10, 2, 15, 0, tzinfo=timezone.utc),
            is_completed=True,
        )

        await self.meeting_service.upsert_meetings(
            self.mock_session, self.user_context, payload
        )

        self.assertEqual(
            len(self.mock_pair_entity.meeting_log["google_meetings"]),
            1,
            "manual submit must not drop the other generation's entries",
        )
        self.assertEqual(len(self.mock_pair_entity.meeting_log["meeting_time_list"]), 1)
        self.assertEqual(
            self.mock_pair_entity.completed_count,
            2,
            "completed_count must sum both generations",
        )


class TestMeetingServiceV2(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.mock_logger = MagicMock()
        self.mock_users_repository = MagicMock()
        self.mock_users_repository.get_user_by_user_id = AsyncMock()
        self.mock_mentorship_pairs_repository = MagicMock()
        self.mock_mentorship_pairs_repository.get_pair_with_partner_by_round_and_users_and_status = AsyncMock()
        self.mock_mentorship_pairs_repository.append_google_meeting = AsyncMock()

        self.mock_session = AsyncMock()

        # Address resolution, the idempotent insert and opening the Meet
        # space now live in the shared MeetingSchedulingService; that
        # service's own behaviour is covered by
        # tests/backend_test/communication_test/meeting_scheduling_service_test.py.
        # This mock only needs to hand back its normalized result shape.
        self.scheduled_meeting = {
            "google_event_id": "google_event_123",
            "meet_link": "https://meet.google.com/abc-def-ghi",
            "entry_points": [
                {
                    "entryPointType": "video",
                    "uri": "https://meet.google.com/abc-def-ghi",
                }
            ],
            "conference_id": "abc-def-ghi",
            "created": "",
        }
        self.mock_meeting_scheduling_service = AsyncMock()
        self.mock_meeting_scheduling_service.schedule = AsyncMock(
            return_value=self.scheduled_meeting
        )
        self.mock_meeting_scheduling_service.cancel = AsyncMock(return_value=([], []))

        self.service = MeetingService(
            logger=self.mock_logger,
            mentorship_pairs_repository=self.mock_mentorship_pairs_repository,
            mentorship_mapper=MagicMock(),
            users_repository=self.mock_users_repository,
            meeting_scheduling_service=self.mock_meeting_scheduling_service,
            mentorship_calendar_id="cal-mentorship",
        )

        self.mock_current_user = MagicMock()
        self.mock_current_user.user_id = 1
        self.mock_current_user.preferred_name = "Alice"
        self.mock_current_user.first_name = "Alice"
        self.mock_current_user.primary_email = "alice@example.com"

        self.mock_partner = MagicMock()
        self.mock_partner.user_id = 2
        self.mock_partner.preferred_name = "Bob"
        self.mock_partner.first_name = "Bob"
        self.mock_partner.primary_email = "bob@example.com"

        self.mock_users_repository.get_user_by_user_id.return_value = (
            self.mock_current_user
        )

        self.mock_pair = MagicMock()
        self.mock_pair.meeting_log = None
        self.mock_mentorship_pairs_repository.get_pair_with_partner_by_round_and_users_and_status.return_value = (
            self.mock_pair,
            self.mock_partner,
        )

        self.user_context = MagicMock(
            spec=UserContextDto,
            user_id=1,
            identity_type="external",
        )
        self.start_dt = datetime(2026, 3, 20, 10, 0, tzinfo=timezone.utc)
        self.end_dt = datetime(2026, 3, 20, 11, 0, tzinfo=timezone.utc)

        self.mock_pairs_repo = self.mock_mentorship_pairs_repository
        self.mock_pairs_repo.get_pairs_by_user_and_round = AsyncMock()

        self.mock_mapper = MagicMock()

        self.meeting_service = MeetingService(
            logger=self.mock_logger,
            mentorship_pairs_repository=self.mock_pairs_repo,
            mentorship_mapper=self.mock_mapper,
            users_repository=self.mock_users_repository,
            meeting_scheduling_service=self.mock_meeting_scheduling_service,
            mentorship_calendar_id="cal-mentorship",
        )

        self.user_id = 1
        self.round_id = 10
        self.partner_id = 100

        self.mock_current_user.timezone = "America/New_York"

        self.user_context.has_permission.return_value = False

        self.mock_pair_entity = MagicMock(
            spec=MentorshipPairsEntity,
            mentor_id=self.partner_id,
            mentee_id=self.user_id,
            completed_count=3,
            meeting_log={
                "meeting_time_list": [
                    {
                        "meeting_id": "m-1",
                        "start_datetime": "2025-10-01T10:00:00Z",
                        "end_datetime": "2025-10-01T11:00:00Z",
                        "is_completed": True,
                    }
                ],
                "google_meetings": [],
            },
        )

        self.mock_users_repository.get_user_by_user_id.return_value = (
            self.mock_current_user
        )

        # session_factory yields the shared mock session as an async CM
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=self.mock_session)
        cm.__aexit__ = AsyncMock(return_value=None)
        self.mock_session_factory = MagicMock(return_value=cm)

    async def test_create_google_meeting_success(self):
        """Test successful meeting creation with correct response fields."""
        result = await self.service.create_google_meeting(
            session=self.mock_session,
            user_context=self.user_context,
            partner_id=2,
            round_id=1,
            start_datetime=self.start_dt,
            end_datetime=self.end_dt,
        )

        self.assertIsInstance(result, GoogleMeetingResponseDetailDto)
        self.assertEqual(result.meeting_id, "google_event_123")
        self.assertEqual(result.meet_link, "https://meet.google.com/abc-def-ghi")
        self.assertEqual(result.attendees, [1, 2])
        self.assertEqual(result.start_datetime, self.start_dt.isoformat())
        self.assertEqual(result.end_datetime, self.end_dt.isoformat())
        self.assertFalse(result.is_completed)
        self.assertEqual(len(result.entry_points), 1)

    async def test_create_google_meeting_calls_scheduling_service_with_correct_args(
        self,
    ):
        """Test that the shared scheduling service is called with correct summary/times/attendees.

        Address resolution, the idempotent insert and opening the Meet space
        are MeetingSchedulingService's job now (see
        meeting_scheduling_service_test.py); this only checks the hand-off.
        """
        await self.service.create_google_meeting(
            session=self.mock_session,
            user_context=self.user_context,
            partner_id=2,
            round_id=1,
            start_datetime=self.start_dt,
            end_datetime=self.end_dt,
        )

        call_args, call_kwargs = self.mock_meeting_scheduling_service.schedule.call_args
        self.assertEqual(call_args[0], self.mock_session)
        self.assertEqual(call_kwargs["summary"], "Circlecat Mentorship - Alice / Bob")
        self.assertEqual(call_kwargs["start_utc"], self.start_dt)
        self.assertEqual(call_kwargs["end_utc"], self.end_dt)
        self.assertEqual(call_kwargs["attendee_user_ids"], [1, 2])
        # The injected container must reach the shared service. Note that
        # service is an AsyncMock here, so nothing else in this file would go
        # red if MeetingService stopped passing it -- this assertion is the
        # only guard against silently falling back to the shared calendar.
        self.assertEqual(call_kwargs["calendar_id"], "cal-mentorship")

    async def test_create_google_meeting_persists_meeting_log(self):
        """Test that meeting result is persisted to meeting_log."""
        await self.service.create_google_meeting(
            session=self.mock_session,
            user_context=self.user_context,
            partner_id=2,
            round_id=1,
            start_datetime=self.start_dt,
            end_datetime=self.end_dt,
        )

        self.mock_mentorship_pairs_repository.get_pair_with_partner_by_round_and_users_and_status.assert_awaited_once_with(
            session=self.mock_session,
            round_id=1,
            user_id=1,
            partner_id=2,
            status=PairStatus.ACTIVE,
            with_lock=True,
        )
        call_kwargs = (
            self.mock_mentorship_pairs_repository.append_google_meeting.call_args.kwargs
        )
        self.assertEqual(call_kwargs["pair_id"], self.mock_pair.pair_id)
        self.assertEqual(call_kwargs["meeting_entry"]["meeting_id"], "google_event_123")
        self.assertFalse(call_kwargs["meeting_entry"]["is_completed"])
        self.mock_session.commit.assert_awaited_once()

    async def test_create_google_meeting_partner_not_found(self):
        """Test that ValueError is raised when pair does not exist."""
        self.mock_mentorship_pairs_repository.get_pair_with_partner_by_round_and_users_and_status.return_value = None

        with self.assertRaises(ValueError) as ctx:
            await self.service.create_google_meeting(
                session=self.mock_session,
                user_context=self.user_context,
                partner_id=999,
                round_id=1,
                start_datetime=self.start_dt,
                end_datetime=self.end_dt,
            )

        self.assertIn("No mentorship pair found", str(ctx.exception))
        self.mock_meeting_scheduling_service.schedule.assert_not_awaited()

    async def test_create_google_meeting_uses_full_name_when_no_preferred_name(self):
        """Test fallback to the full 'first last' name when preferred_name is None."""
        self.mock_current_user.preferred_name = None
        self.mock_current_user.first_name = "AliceFirst"
        self.mock_current_user.last_name = "AliceLast"
        self.mock_partner.preferred_name = None
        self.mock_partner.first_name = "BobFirst"
        self.mock_partner.last_name = "BobLast"

        await self.service.create_google_meeting(
            session=self.mock_session,
            user_context=self.user_context,
            partner_id=2,
            round_id=1,
            start_datetime=self.start_dt,
            end_datetime=self.end_dt,
        )

        call_kwargs = self.mock_meeting_scheduling_service.schedule.call_args.kwargs
        self.assertEqual(
            call_kwargs["summary"],
            "Circlecat Mentorship - AliceFirst AliceLast / BobFirst BobLast",
        )

    async def test_get_meetings_by_user_and_round_v2_success(self):
        """Test retrieved and mapped meeting logs for a matched user correctly in v2."""
        self.mock_pairs_repo.get_pairs_by_user_and_round.return_value = [
            self.mock_pair_entity
        ]

        self.user_context.has_permission.return_value = True
        stub_dto = MagicMock(spec=MeetingDto)
        self.mock_mapper.map_to_meeting_v2_dto.return_value = stub_dto

        result = await self.meeting_service.get_meetings_by_user_and_round_v2(
            self.mock_session,
            self.user_context,
            self.round_id,
            include_details=True,
        )

        self.assertEqual(result, stub_dto)
        self.mock_pairs_repo.get_pairs_by_user_and_round.assert_awaited_once_with(
            session=self.mock_session,
            user_id=self.user_id,
            round_id=self.round_id,
        )
        self.mock_mapper.map_to_meeting_v2_dto.assert_called_once_with(
            round_id=self.round_id,
            user_timezone=self.mock_current_user.timezone,
            grouped_pairs=[(self.mock_pair_entity, self.partner_id)],
            include_details=True,
        )
        self.user_context.has_permission.assert_called_once_with(
            Permission.MENTORSHIP_ADMIN_READ
        )

    async def test_get_meetings_by_user_and_round_v2_no_pair_found(self):
        """Verify that an empty MeetingDto is returned when no mentorship pairs exist in v2."""
        self.user_context.has_permission.return_value = False
        self.mock_pairs_repo.get_pairs_by_user_and_round.return_value = []

        result = await self.meeting_service.get_meetings_by_user_and_round_v2(
            self.mock_session,
            self.user_context,
            self.round_id,
            include_details=False,
        )

        self.assertIsInstance(result, MeetingDto)
        self.assertEqual(result.round_id, self.round_id)
        self.assertEqual(result.user_timezone, "America/New_York")
        self.assertEqual(len(result.meeting_info), 0)

        self.mock_mapper.map_to_meeting_v2_dto.assert_not_called()

    async def test_get_meetings_by_user_and_round_v2_non_admin_detail_not_allowed(self):
        """Verify detail fields are not allowed for non-admin users even when include_details=True."""
        self.mock_pairs_repo.get_pairs_by_user_and_round.return_value = [
            self.mock_pair_entity
        ]
        self.user_context.has_permission.return_value = False

        stub_dto = MagicMock(spec=MeetingDto)
        self.mock_mapper.map_to_meeting_v2_dto.return_value = stub_dto

        await self.meeting_service.get_meetings_by_user_and_round_v2(
            self.mock_session,
            self.user_context,
            self.round_id,
            include_details=True,
        )

        self.mock_mapper.map_to_meeting_v2_dto.assert_called_once_with(
            round_id=self.round_id,
            user_timezone=self.mock_current_user.timezone,
            grouped_pairs=[(self.mock_pair_entity, self.partner_id)],
            include_details=False,
        )

    async def test_delete_google_meetings_success(self):
        """Verify successful deletion removes Google-deleted meetings from DB and commits."""
        self.mock_mentorship_pairs_repository.do_google_meetings_exist_in_log = (
            AsyncMock(return_value=True)
        )
        self.mock_mentorship_pairs_repository.remove_meetings_from_log = AsyncMock(
            return_value=[1]
        )
        self.mock_meeting_scheduling_service.cancel.return_value = (
            ["abc"],
            [],
        )

        result = await self.service.delete_google_meetings(
            session=self.mock_session,
            user_context=self.user_context,
            deletions=[
                {
                    "round_id": 1,
                    "partner_id": 2,
                    "meeting_ids": ["abc"],
                }
            ],
        )

        self.mock_mentorship_pairs_repository.do_google_meetings_exist_in_log.assert_awaited_once()
        self.mock_meeting_scheduling_service.cancel.assert_awaited_once_with(
            ["abc"], calendar_id="cal-mentorship"
        )
        self.mock_mentorship_pairs_repository.remove_meetings_from_log.assert_awaited_once_with(
            session=self.mock_session,
            user_id=self.user_id,
            meeting_ids=["abc"],
        )
        self.mock_session.commit.assert_awaited_once()

        self.assertEqual(result.succeeded_meeting_ids, ["abc"])
        self.assertEqual(result.failed_meeting_ids, [])

    async def test_delete_google_meetings_empty_deletions(self):
        """Raises ValueError when deletions is empty."""
        with self.assertRaises(ValueError):
            await self.service.delete_google_meetings(
                session=self.mock_session,
                user_context=self.user_context,
                deletions=[],
            )

    async def test_delete_google_meetings_not_found(self):
        """Raises ValueError when meetings do not exist in log."""

        self.mock_mentorship_pairs_repository.do_google_meetings_exist_in_log = (
            AsyncMock(return_value=False)
        )

        with self.assertRaises(ValueError):
            await self.service.delete_google_meetings(
                session=self.mock_session,
                user_context=self.user_context,
                deletions=[
                    {
                        "round_id": 1,
                        "partner_id": 2,
                        "meeting_ids": ["abc"],
                    }
                ],
            )

    async def test_create_google_meetings_batch_single_success(self):
        """count=1: converts wall-clock to UTC and returns one created entry."""
        from datetime import date

        result = await self.service.create_google_meetings_batch(
            session_factory=self.mock_session_factory,
            user_context=self.user_context,
            partner_id=2,
            round_id=1,
            timezone="America/New_York",
            start_date=date(2026, 7, 30),
            start_time="10:00",
            duration_minutes=30,
        )

        self.assertEqual(len(result.created), 1)
        self.assertEqual(len(result.failed), 0)
        # 10:00 EDT (UTC-4 in July) -> 14:00Z
        call = self.mock_meeting_scheduling_service.schedule.call_args
        self.assertEqual(
            call.kwargs["start_utc"].isoformat(), "2026-07-30T14:00:00+00:00"
        )
        self.assertEqual(
            call.kwargs["end_utc"].isoformat(), "2026-07-30T14:30:00+00:00"
        )

    async def test_create_google_meetings_batch_best_effort_failure(self):
        """A per-occurrence Google failure is captured in `failed`, not raised."""
        from datetime import date

        self.mock_meeting_scheduling_service.schedule.side_effect = RuntimeError("boom")

        result = await self.service.create_google_meetings_batch(
            session_factory=self.mock_session_factory,
            user_context=self.user_context,
            partner_id=2,
            round_id=1,
            timezone="America/New_York",
            start_date=date(2026, 7, 30),
            start_time="10:00",
            duration_minutes=30,
        )

        self.assertEqual(len(result.created), 0)
        self.assertEqual(len(result.failed), 1)
        self.assertEqual(result.failed[0].index, 0)
        self.assertIn("boom", result.failed[0].reason)

    def test_expand_occurrences_weekly_crosses_dst(self):
        """Weekly series keeps local wall-clock time constant across a DST end.

        US DST ends Sun 2026-11-01 (America/New_York EDT UTC-4 -> EST UTC-5).
        Weekly 10:00 local from Oct 22: the occurrence after Nov 1 must stay
        10:00 local, which is 15:00Z (not 14:00Z) -- the UTC offset shifts an
        hour precisely because weeks are added to the naive time before
        localizing.
        """
        from datetime import date

        pairs = self.service._expand_occurrences(
            timezone="America/New_York",
            start_date=date(2026, 10, 22),
            start_time="10:00",
            duration_minutes=30,
            interval_weeks=1,
            count=3,
        )

        starts = [s.isoformat() for s, _ in pairs]
        ends = [e.isoformat() for _, e in pairs]
        self.assertEqual(
            starts,
            [
                "2026-10-22T14:00:00+00:00",
                "2026-10-29T14:00:00+00:00",
                "2026-11-05T15:00:00+00:00",  # DST ended -> +1h in UTC, still 10:00 local
            ],
        )
        self.assertEqual(
            ends,
            [
                "2026-10-22T14:30:00+00:00",
                "2026-10-29T14:30:00+00:00",
                "2026-11-05T15:30:00+00:00",
            ],
        )

    def test_expand_occurrences_biweekly_crosses_dst(self):
        """Bi-weekly (interval_weeks=2) spacing is 14 days and DST-correct."""
        from datetime import date

        pairs = self.service._expand_occurrences(
            timezone="America/New_York",
            start_date=date(2026, 10, 22),
            start_time="10:00",
            duration_minutes=30,
            interval_weeks=2,
            count=2,
        )

        starts = [s.isoformat() for s, _ in pairs]
        self.assertEqual(
            starts,
            [
                "2026-10-22T14:00:00+00:00",
                "2026-11-05T15:00:00+00:00",  # 14 days later, after DST end
            ],
        )

    async def test_create_google_meetings_batch_multi_occurrence_dst(self):
        """count>1 creates N meetings, each at the DST-correct UTC instant."""
        from datetime import date

        result = await self.service.create_google_meetings_batch(
            session_factory=self.mock_session_factory,
            user_context=self.user_context,
            partner_id=2,
            round_id=1,
            timezone="America/New_York",
            start_date=date(2026, 10, 22),
            start_time="10:00",
            duration_minutes=30,
            interval_weeks=1,
            count=3,
        )

        self.assertEqual(len(result.created), 3)
        self.assertEqual(len(result.failed), 0)
        self.assertEqual(self.mock_meeting_scheduling_service.schedule.call_count, 3)
        actual_starts = [
            c.kwargs["start_utc"].isoformat()
            for c in self.mock_meeting_scheduling_service.schedule.call_args_list
        ]
        self.assertEqual(
            actual_starts,
            [
                "2026-10-22T14:00:00+00:00",
                "2026-10-29T14:00:00+00:00",
                "2026-11-05T15:00:00+00:00",
            ],
        )


if __name__ == "__main__":
    unittest.main()
