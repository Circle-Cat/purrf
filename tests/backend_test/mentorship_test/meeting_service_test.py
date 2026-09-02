import copy
import unittest
import uuid
from datetime import date, datetime, timezone
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
from backend.entity.mentorship_meeting_entity import MentorshipMeetingEntity
from backend.common.mentorship_enums import MeetingSource, PairStatus
from backend.common.permissions import Permission
from backend.common.exceptions import MeetingGoneError


class TestMeetingServiceV1(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.mock_logger = MagicMock()
        self.mock_pairs_repo = MagicMock()
        self.mock_pairs_repo.get_pairs_by_user_and_round = AsyncMock()
        self.mock_pairs_repo.get_active_pair_by_mentee_and_mentor = AsyncMock()
        self.mock_pairs_repo.upsert_pairs = AsyncMock()

        self.mock_mapper = MagicMock()
        self.mock_users_repo = MagicMock()
        self.mock_users_repo.get_user_by_user_id = AsyncMock()
        self.mock_session = AsyncMock()

        self.mock_meeting_repo = MagicMock()
        self.mock_meeting_repo.get_meetings_by_pair = AsyncMock()
        self.mock_meeting_repo.get_meetings_by_pairs = AsyncMock()
        self.mock_meeting_repo.count_completed_by_pairs = AsyncMock(return_value={})
        self.mock_meeting_repo.insert_meeting = AsyncMock()
        self.mock_meeting_repo.recalculate_completed_count = AsyncMock()

        self.mock_meeting_scheduling_service = AsyncMock()
        self.meeting_service = MeetingService(
            logger=self.mock_logger,
            mentorship_pairs_repository=self.mock_pairs_repo,
            mentorship_mapper=self.mock_mapper,
            users_repository=self.mock_users_repo,
            meeting_scheduling_service=self.mock_meeting_scheduling_service,
            mentorship_calendar_id="cal-mentorship",
            mentorship_meeting_repository=self.mock_meeting_repo,
        )

        self.user_id = 1
        self.round_id = 10
        self.partner_id = 100
        self.pair_id = 55
        self.user_context = MagicMock(
            spec=UserContextDto,
            sub="sub-123",
            user_id=self.user_id,
            identity_type="external",
        )
        self.mock_current_user = MagicMock(spec=UsersEntity, user_id=self.user_id)
        self.mock_current_user.timezone = "America/New_York"
        self.mock_users_repo.get_user_by_user_id.return_value = self.mock_current_user

        # meeting_log is a deliberately stale JSONB snapshot -- this generation's
        # code must never read or write it. Kept around only so a regression
        # (writing to it) would show up as a mutation the tests can catch.
        self.original_meeting_log = {
            "meeting_time_list": [
                {
                    "meeting_id": "m-1",
                    "start_datetime": "2025-10-01T10:00:00Z",
                    "end_datetime": "2025-10-01T11:00:00Z",
                    "is_completed": True,
                    "created_datetime": "2025-09-30T09:00:00Z",
                }
            ],
        }
        self.mock_pair_entity = MagicMock(
            spec=MentorshipPairsEntity,
            pair_id=self.pair_id,
            mentor_id=self.partner_id,
            mentee_id=self.user_id,
            completed_count=3,
            # Deep copy is deliberate, not defensive boilerplate: a shallow
            # `dict(...)` here would leave `meeting_time_list` as the SAME
            # list object as `self.original_meeting_log`'s, so an in-place
            # `.append()` regression on the inner list would go undetected by
            # any `assertEqual` snapshot comparison below.
            meeting_log=copy.deepcopy(self.original_meeting_log),
        )

        self.existing_manual_meeting = MagicMock(
            spec=MentorshipMeetingEntity,
            meeting_id="m-1",
            pair_id=self.pair_id,
            source=MeetingSource.MANUAL,
            start_datetime=datetime(2025, 10, 1, 10, 0, tzinfo=timezone.utc),
            end_datetime=datetime(2025, 10, 1, 11, 0, tzinfo=timezone.utc),
            is_completed=True,
            created_datetime=datetime(2025, 9, 30, 9, 0, tzinfo=timezone.utc),
        )
        self.existing_google_meeting = MagicMock(
            spec=MentorshipMeetingEntity,
            meeting_id="evt-1",
            pair_id=self.pair_id,
            source=MeetingSource.GOOGLE,
            start_datetime=datetime(2025, 10, 3, 10, 0, tzinfo=timezone.utc),
            end_datetime=datetime(2025, 10, 3, 11, 0, tzinfo=timezone.utc),
            is_completed=False,
            created_datetime=datetime(2025, 10, 1, 9, 0, tzinfo=timezone.utc),
        )

    async def test_get_meetings_by_user_and_round_success(self):
        """Test retrieved and mapped meeting logs for a matched user correctly."""
        self.mock_pairs_repo.get_pairs_by_user_and_round.return_value = [
            self.mock_pair_entity
        ]
        self.mock_meeting_repo.get_meetings_by_pairs.return_value = {
            self.pair_id: [self.existing_manual_meeting]
        }
        stub_dto = MagicMock(spec=MeetingDto)
        self.mock_mapper.map_to_meeting_dto.return_value = stub_dto

        result = await self.meeting_service.get_meetings_by_user_and_round(
            self.mock_session, self.user_context, self.round_id
        )

        self.assertEqual(result, stub_dto)
        self.mock_pairs_repo.get_pairs_by_user_and_round.assert_awaited_once_with(
            session=self.mock_session, user_id=self.user_id, round_id=self.round_id
        )
        self.mock_meeting_repo.get_meetings_by_pairs.assert_awaited_once_with(
            session=self.mock_session, pair_ids=[self.pair_id]
        )
        self.mock_mapper.map_to_meeting_dto.assert_called_once_with(
            round_id=self.round_id,
            grouped_pairs=[(self.mock_pair_entity, self.partner_id)],
            meetings_by_pair={self.pair_id: [self.existing_manual_meeting]},
            completed_counts={},
        )

    async def test_get_meetings_by_user_and_round_v1_read_is_manual_only(self):
        """IMPORTANT 2 pin: the v1 read must keep its old MANUAL-only contract.

        `get_meetings_by_pairs` returns both MANUAL and GOOGLE rows for a pair
        (only LEGACY is excluded by the repository itself); this method must
        filter GOOGLE back out before handing anything to the mapper, or a
        pair whose round switched from v1 to v2 would suddenly show its
        Google meetings on a dashboard that never displayed them before.
        """
        self.mock_pairs_repo.get_pairs_by_user_and_round.return_value = [
            self.mock_pair_entity
        ]
        self.mock_meeting_repo.get_meetings_by_pairs.return_value = {
            self.pair_id: [self.existing_manual_meeting, self.existing_google_meeting]
        }
        stub_dto = MagicMock(spec=MeetingDto)
        self.mock_mapper.map_to_meeting_dto.return_value = stub_dto

        await self.meeting_service.get_meetings_by_user_and_round(
            self.mock_session, self.user_context, self.round_id
        )

        passed_meetings_by_pair = self.mock_mapper.map_to_meeting_dto.call_args.kwargs[
            "meetings_by_pair"
        ]
        self.assertEqual(
            passed_meetings_by_pair, {self.pair_id: [self.existing_manual_meeting]}
        )

    async def test_get_meetings_by_user_and_round_no_pair_found(self):
        """Verify that an empty MeetingDto is returned when no mentorship pairs exist."""
        self.mock_pairs_repo.get_pairs_by_user_and_round.return_value = []

        result = await self.meeting_service.get_meetings_by_user_and_round(
            self.mock_session, self.user_context, self.round_id
        )

        self.assertIsInstance(result, MeetingDto)
        self.assertEqual(result.round_id, self.round_id)
        self.assertEqual(len(result.meeting_info), 0)

        self.mock_mapper.map_to_meeting_dto.assert_not_called()

    async def test_upsert_meetings_success(self):
        """New meeting slots are validated, inserted as a row, and counted via
        the repository -- not by rewriting meeting_log."""
        self.mock_pairs_repo.get_active_pair_by_mentee_and_mentor.return_value = (
            self.mock_pair_entity
        )
        # First call: pre-insert conflict check finds no overlap. Second call:
        # post-insert read used to build the response DTO.
        self.mock_meeting_repo.get_meetings_by_pair.side_effect = [
            [],
            [self.existing_manual_meeting],
        ]
        self.mock_meeting_repo.recalculate_completed_count.return_value = 4

        payload = MeetingCreateDto(
            round_id=self.round_id,
            partner_id=self.partner_id,
            start_datetime=datetime(2025, 10, 1, 14, 0, tzinfo=timezone.utc),
            end_datetime=datetime(2025, 10, 1, 15, 0, tzinfo=timezone.utc),
            is_completed=True,
        )

        await self.meeting_service.upsert_meetings(
            self.mock_session, self.user_context, payload
        )

        self.mock_meeting_repo.insert_meeting.assert_awaited_once()
        inserted_meeting = self.mock_meeting_repo.insert_meeting.await_args.kwargs[
            "meeting"
        ]
        self.assertIsInstance(inserted_meeting, MentorshipMeetingEntity)
        self.assertEqual(inserted_meeting.pair_id, self.pair_id)
        self.assertEqual(inserted_meeting.source, MeetingSource.MANUAL)
        self.assertEqual(inserted_meeting.start_datetime, payload.start_datetime)
        self.assertEqual(inserted_meeting.end_datetime, payload.end_datetime)
        self.assertTrue(inserted_meeting.is_completed)
        # assertEqual(...version, 4) rather than assertTrue(uuid.UUID(x)):
        # the latter only proves the string parses as *some* UUID (it would
        # pass for a uuid1 too), not specifically the uuid4 the code asks for.
        self.assertEqual(uuid.UUID(inserted_meeting.meeting_id).version, 4)

        self.mock_meeting_repo.recalculate_completed_count.assert_awaited_once_with(
            session=self.mock_session, pair_id=self.pair_id
        )
        self.assertEqual(self.mock_pair_entity.completed_count, 4)

        # The single most important assertion in this slice: switching to the
        # table must not also keep writing the JSONB column.
        self.mock_pairs_repo.upsert_pairs.assert_not_awaited()
        self.assertEqual(self.mock_pair_entity.meeting_log, self.original_meeting_log)

        self.mock_session.commit.assert_awaited_once()

    async def test_upsert_meetings_conflict(self):
        """Test overlapping meeting times trigger a validation error."""
        self.mock_pairs_repo.get_active_pair_by_mentee_and_mentor.return_value = (
            self.mock_pair_entity
        )
        self.mock_meeting_repo.get_meetings_by_pair.return_value = [
            self.existing_manual_meeting
        ]
        payload = MeetingCreateDto(
            round_id=self.round_id,
            partner_id=self.partner_id,
            start_datetime=datetime(2025, 10, 1, 10, 30, tzinfo=timezone.utc),
            end_datetime=datetime(2025, 10, 1, 11, 30, tzinfo=timezone.utc),
            is_completed=True,
        )

        with self.assertRaisesRegex(ValueError, "This time slot already exists."):
            await self.meeting_service.upsert_meetings(
                self.mock_session, self.user_context, payload
            )

        self.mock_meeting_repo.insert_meeting.assert_not_awaited()
        self.mock_meeting_repo.recalculate_completed_count.assert_not_awaited()
        self.mock_pairs_repo.upsert_pairs.assert_not_awaited()
        self.mock_session.commit.assert_not_awaited()

    async def test_upsert_meetings_ignores_google_meetings_for_conflict(self):
        """Conflict-checking must only compare against MANUAL rows, matching
        the old behavior of comparing only against `meeting_time_list` and
        never `google_meetings`."""
        google_meeting = MagicMock(
            spec=MentorshipMeetingEntity,
            meeting_id="evt-1",
            pair_id=self.pair_id,
            source=MeetingSource.GOOGLE,
            start_datetime=datetime(2025, 10, 1, 14, 0, tzinfo=timezone.utc),
            end_datetime=datetime(2025, 10, 1, 15, 0, tzinfo=timezone.utc),
            is_completed=False,
        )
        self.mock_pairs_repo.get_active_pair_by_mentee_and_mentor.return_value = (
            self.mock_pair_entity
        )
        self.mock_meeting_repo.get_meetings_by_pair.side_effect = [
            [google_meeting],
            [google_meeting],
        ]
        self.mock_meeting_repo.recalculate_completed_count.return_value = 4

        # Exactly overlaps the GOOGLE meeting above; must NOT raise.
        payload = MeetingCreateDto(
            round_id=self.round_id,
            partner_id=self.partner_id,
            start_datetime=datetime(2025, 10, 1, 14, 0, tzinfo=timezone.utc),
            end_datetime=datetime(2025, 10, 1, 15, 0, tzinfo=timezone.utc),
            is_completed=True,
        )

        await self.meeting_service.upsert_meetings(
            self.mock_session, self.user_context, payload
        )

        self.mock_meeting_repo.insert_meeting.assert_awaited_once()

    async def test_upsert_meetings_does_not_modify_meeting_log(self):
        """Dedicated pin: upsert_meetings must not touch meeting_log at all,
        even when the pair already has both generations recorded there."""
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
        # Deep copy for the same reason as the setUp fixture above -- a
        # shallow copy would share the inner lists with the live entity and
        # miss an in-place `.append()` regression.
        untouched_snapshot = copy.deepcopy(self.mock_pair_entity.meeting_log)
        self.mock_pairs_repo.get_active_pair_by_mentee_and_mentor.return_value = (
            self.mock_pair_entity
        )
        self.mock_meeting_repo.get_meetings_by_pair.side_effect = [[], []]
        self.mock_meeting_repo.recalculate_completed_count.return_value = 1

        payload = MeetingCreateDto(
            round_id=self.round_id,
            partner_id=self.partner_id,
            start_datetime=datetime(2025, 10, 2, 14, 0, tzinfo=timezone.utc),
            end_datetime=datetime(2025, 10, 2, 15, 0, tzinfo=timezone.utc),
            is_completed=True,
        )

        await self.meeting_service.upsert_meetings(
            self.mock_session, self.user_context, payload
        )

        self.assertEqual(self.mock_pair_entity.meeting_log, untouched_snapshot)
        self.mock_pairs_repo.upsert_pairs.assert_not_awaited()

    async def test_upsert_meetings_resolves_the_pair_by_the_named_partner(self):
        """The pair is looked up by the partner the payload names, with the
        current user pinned to the mentee side -- a mentee can hold several
        pairs in one round, so the round alone does not identify one."""
        self.mock_pairs_repo.get_active_pair_by_mentee_and_mentor.return_value = (
            self.mock_pair_entity
        )
        self.mock_meeting_repo.get_meetings_by_pair.side_effect = [[], []]
        self.mock_meeting_repo.recalculate_completed_count.return_value = 1

        payload = MeetingCreateDto(
            round_id=self.round_id,
            partner_id=self.partner_id,
            start_datetime=datetime(2025, 10, 3, 14, 0, tzinfo=timezone.utc),
            end_datetime=datetime(2025, 10, 3, 15, 0, tzinfo=timezone.utc),
            is_completed=True,
        )

        await self.meeting_service.upsert_meetings(
            self.mock_session, self.user_context, payload
        )

        self.mock_pairs_repo.get_active_pair_by_mentee_and_mentor.assert_awaited_once_with(
            session=self.mock_session,
            mentee_id=self.user_id,
            mentor_id=self.partner_id,
            round_id=self.round_id,
        )

    async def test_upsert_meetings_no_active_pair(self):
        """No active pair with the named partner is rejected before any write.

        This is the path a partner whose pair has ended takes: the lookup
        returns None rather than matching the ended pair.
        """
        self.mock_pairs_repo.get_active_pair_by_mentee_and_mentor.return_value = None

        payload = MeetingCreateDto(
            round_id=self.round_id,
            partner_id=self.partner_id,
            start_datetime=datetime(2025, 10, 4, 14, 0, tzinfo=timezone.utc),
            end_datetime=datetime(2025, 10, 4, 15, 0, tzinfo=timezone.utc),
            is_completed=True,
        )

        with self.assertRaisesRegex(ValueError, "not actively matched"):
            await self.meeting_service.upsert_meetings(
                self.mock_session, self.user_context, payload
            )

        self.mock_meeting_repo.insert_meeting.assert_not_awaited()
        self.mock_meeting_repo.recalculate_completed_count.assert_not_awaited()
        self.mock_session.commit.assert_not_awaited()

    async def test_upsert_meetings_requires_partner_id(self):
        """The v1 payload cannot omit the partner: without it the request
        cannot say which pair the meeting belongs to."""
        with self.assertRaises(ValueError):
            MeetingCreateDto(
                round_id=self.round_id,
                start_datetime=datetime(2025, 10, 5, 14, 0, tzinfo=timezone.utc),
                end_datetime=datetime(2025, 10, 5, 15, 0, tzinfo=timezone.utc),
                is_completed=True,
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

        self.mock_meeting_repo = MagicMock()
        self.mock_meeting_repo.insert_meeting = AsyncMock()
        self.mock_meeting_repo.get_meetings_by_pair = AsyncMock(return_value=[])
        self.mock_meeting_repo.get_meetings_by_pairs = AsyncMock(return_value={})
        self.mock_meeting_repo.count_completed_by_pairs = AsyncMock(return_value={})
        self.mock_meeting_repo.delete_meetings = AsyncMock()
        self.mock_meeting_repo.recalculate_completed_count = AsyncMock()

        self.service = MeetingService(
            logger=self.mock_logger,
            mentorship_pairs_repository=self.mock_mentorship_pairs_repository,
            mentorship_mapper=MagicMock(),
            users_repository=self.mock_users_repository,
            meeting_scheduling_service=self.mock_meeting_scheduling_service,
            mentorship_calendar_id="cal-mentorship",
            mentorship_meeting_repository=self.mock_meeting_repo,
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
            mentorship_meeting_repository=self.mock_meeting_repo,
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

    async def test_create_google_meeting_persists_meeting_row(self):
        """Test that meeting result is persisted as a mentorship_meeting row,
        not appended to meeting_log."""
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
        self.mock_meeting_repo.insert_meeting.assert_awaited_once()
        inserted_meeting = self.mock_meeting_repo.insert_meeting.await_args.kwargs[
            "meeting"
        ]
        self.assertIsInstance(inserted_meeting, MentorshipMeetingEntity)
        self.assertEqual(inserted_meeting.pair_id, self.mock_pair.pair_id)
        self.assertEqual(inserted_meeting.source, MeetingSource.GOOGLE)
        self.assertEqual(inserted_meeting.meeting_id, "google_event_123")
        self.assertEqual(
            inserted_meeting.meet_link, "https://meet.google.com/abc-def-ghi"
        )
        # `conference_id` is the scheduling service's key name for what this
        # column calls `google_meeting_code` -- a deliberate rename, not a
        # bug, at the boundary between the two.
        self.assertEqual(inserted_meeting.google_meeting_code, "abc-def-ghi")
        self.assertEqual(
            inserted_meeting.entry_points, self.scheduled_meeting["entry_points"]
        )
        self.assertFalse(inserted_meeting.is_completed)
        self.assertEqual(inserted_meeting.start_datetime, self.start_dt)
        self.assertEqual(inserted_meeting.end_datetime, self.end_dt)

        self.mock_mentorship_pairs_repository.append_google_meeting.assert_not_called()
        self.mock_session.commit.assert_awaited_once()

    async def test_create_google_meeting_does_not_modify_meeting_log(self):
        """Pin: creating a Google meeting must write ONLY the table -- the
        pair's `meeting_log` JSONB column must stay byte-for-byte the same.

        `copy.deepcopy` is deliberate, not defensive boilerplate: a shallow
        copy here would leave the inner lists as the SAME objects as the
        live entity's, so an in-place mutation regression would go
        undetected by `assertEqual` below.
        """
        self.mock_pair.meeting_log = {
            "meeting_time_list": [
                {
                    "meeting_id": "m-1",
                    "start_datetime": "2025-10-01T10:00:00Z",
                    "end_datetime": "2025-10-01T11:00:00Z",
                    "is_completed": True,
                    "created_datetime": "2025-09-30T09:00:00Z",
                }
            ],
            "google_meetings": [],
        }
        original_meeting_log = copy.deepcopy(self.mock_pair.meeting_log)

        await self.service.create_google_meeting(
            session=self.mock_session,
            user_context=self.user_context,
            partner_id=2,
            round_id=1,
            start_datetime=self.start_dt,
            end_datetime=self.end_dt,
        )

        self.assertEqual(self.mock_pair.meeting_log, original_meeting_log)
        self.mock_mentorship_pairs_repository.append_google_meeting.assert_not_called()

    async def test_create_google_meeting_uses_google_created_timestamp(self):
        """When Calendar reports a `created` timestamp, the row's
        `created_datetime` must carry Google's value, not the moment this
        code happens to run -- it is exposed via the API and is the
        `_MEETING_ORDER_BY` tiebreaker when two meetings share a
        start_datetime. Getting this wrong matters most exactly on a DB-write
        retry: Calendar's insert is idempotent on the client-minted event id,
        so a retry must still record the meeting's original creation time,
        not the retry's."""
        self.mock_meeting_scheduling_service.schedule.return_value = {
            **self.scheduled_meeting,
            "created": "2025-01-01T10:00:00.000Z",
        }

        await self.service.create_google_meeting(
            session=self.mock_session,
            user_context=self.user_context,
            partner_id=2,
            round_id=1,
            start_datetime=self.start_dt,
            end_datetime=self.end_dt,
        )

        inserted_meeting = self.mock_meeting_repo.insert_meeting.await_args.kwargs[
            "meeting"
        ]
        self.assertEqual(
            inserted_meeting.created_datetime,
            datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc),
        )

    async def test_create_google_meeting_omits_created_datetime_when_google_omits_it(
        self,
    ):
        """When Calendar's `created` is missing/empty, `created_datetime` must
        be left UNSET on the entity -- not explicitly assigned None -- so the
        column's NOT NULL `server_default` fills it in at insert time.
        SQLAlchemy only omits a column from the INSERT when the attribute was
        never assigned at all; explicitly assigning None would insert NULL
        and raise NotNullViolation.

        Checking `vars(...)` rather than the attribute's *value* is
        deliberate and is the point of this test: a naive
        `getattr(..., "created_datetime") is None` check would pass equally
        well for the buggy `created_datetime=None` case, since an unset
        InstrumentedAttribute also reads back as None through a normal
        attribute access -- it would not have caught the NotNullViolation
        this pins against. Inspecting the instance's `__dict__` is what
        actually distinguishes "never set" (key absent, so
        `mapper._collect_insert_commands`-style unit-of-work logic leaves the
        column out of the INSERT and the server_default applies) from
        "explicitly set to None" (key present with value None, which DOES
        get sent as an explicit NULL) -- i.e. it exercises the same
        attribute-presence check the real INSERT path relies on, without
        needing a live database.
        """
        self.mock_meeting_scheduling_service.schedule.return_value = {
            **self.scheduled_meeting,
            "created": "",
        }

        await self.service.create_google_meeting(
            session=self.mock_session,
            user_context=self.user_context,
            partner_id=2,
            round_id=1,
            start_datetime=self.start_dt,
            end_datetime=self.end_dt,
        )

        inserted_meeting = self.mock_meeting_repo.insert_meeting.await_args.kwargs[
            "meeting"
        ]
        self.assertNotIn("created_datetime", vars(inserted_meeting))

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
        self.mock_meeting_repo.insert_meeting.assert_not_awaited()

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
        """Test retrieved and mapped meeting logs for a matched user correctly in v2.

        Unlike v1, the v2 read must NOT filter the fetched rows down to
        MANUAL -- both MANUAL and GOOGLE rows from
        `get_meetings_by_pairs` are handed to the mapper as-is; merging both
        generations is `map_to_meeting_v2_dto`'s job.
        """
        self.mock_pairs_repo.get_pairs_by_user_and_round.return_value = [
            self.mock_pair_entity
        ]
        meetings_by_pair = {
            self.mock_pair_entity.pair_id: [
                MagicMock(spec=MentorshipMeetingEntity, source=MeetingSource.MANUAL),
                MagicMock(spec=MentorshipMeetingEntity, source=MeetingSource.GOOGLE),
            ]
        }
        self.mock_meeting_repo.get_meetings_by_pairs.return_value = meetings_by_pair

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
        self.mock_meeting_repo.get_meetings_by_pairs.assert_awaited_once_with(
            session=self.mock_session, pair_ids=[self.mock_pair_entity.pair_id]
        )
        self.mock_mapper.map_to_meeting_v2_dto.assert_called_once_with(
            round_id=self.round_id,
            grouped_pairs=[(self.mock_pair_entity, self.partner_id)],
            meetings_by_pair=meetings_by_pair,
            completed_counts={},
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
            grouped_pairs=[(self.mock_pair_entity, self.partner_id)],
            meetings_by_pair={},
            completed_counts={},
            include_details=False,
        )

    async def test_delete_google_meetings_success(self):
        """Verify successful deletion removes rows from the table, recomputes
        the completed count, and commits. The Calendar-side call is
        untouched -- it is still handed the bare meeting_id (the Calendar
        event id for a GOOGLE row)."""
        pair = MagicMock(
            spec=MentorshipPairsEntity, pair_id=77, mentor_id=2, mentee_id=1
        )
        self.mock_pairs_repo.get_pairs_by_user_and_round.return_value = [pair]
        existing_google_row = MagicMock(
            spec=MentorshipMeetingEntity,
            meeting_id="abc",
            source=MeetingSource.GOOGLE,
        )
        self.mock_meeting_repo.get_meetings_by_pair.return_value = [existing_google_row]
        self.mock_meeting_repo.delete_meetings.return_value = 1
        self.mock_meeting_repo.recalculate_completed_count.return_value = 5
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

        self.mock_pairs_repo.get_pairs_by_user_and_round.assert_awaited_once_with(
            session=self.mock_session, user_id=self.user_id, round_id=1
        )
        self.mock_meeting_repo.get_meetings_by_pair.assert_awaited_once_with(
            session=self.mock_session, pair_id=77
        )
        self.mock_meeting_scheduling_service.cancel.assert_awaited_once_with(
            ["abc"], calendar_id="cal-mentorship"
        )
        self.mock_meeting_repo.delete_meetings.assert_awaited_once_with(
            session=self.mock_session, pair_id=77, meeting_ids=["abc"]
        )
        self.mock_meeting_repo.recalculate_completed_count.assert_awaited_once_with(
            session=self.mock_session, pair_id=77
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
        """Raises ValueError when the requested meeting id is not among this
        pair's GOOGLE rows -- the existence check now queries the table
        instead of the JSONB log."""
        pair = MagicMock(
            spec=MentorshipPairsEntity, pair_id=77, mentor_id=2, mentee_id=1
        )
        self.mock_pairs_repo.get_pairs_by_user_and_round.return_value = [pair]
        self.mock_meeting_repo.get_meetings_by_pair.return_value = []

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

        self.mock_meeting_scheduling_service.cancel.assert_not_awaited()
        self.mock_meeting_repo.delete_meetings.assert_not_awaited()

    async def test_delete_google_meetings_pair_not_found(self):
        """Raises ValueError when no pair matches round_id/partner_id at all."""
        self.mock_pairs_repo.get_pairs_by_user_and_round.return_value = []

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

        self.mock_meeting_repo.get_meetings_by_pair.assert_not_awaited()
        self.mock_meeting_scheduling_service.cancel.assert_not_awaited()

    async def test_delete_google_meetings_multi_pair_batch_regroups_by_pair(self):
        """A single request can span multiple pairs (the batch-delete
        endpoint sends one `deletions` entry per pair). `delete_meetings` and
        `recalculate_completed_count` are pair-scoped, so each pair must get
        called with exactly ITS OWN ids -- never the union across pairs,
        since `delete_meetings` silently ignores ids for any other pair (an
        authorization boundary, not just tidiness)."""
        pair_a = MagicMock(
            spec=MentorshipPairsEntity, pair_id=77, mentor_id=2, mentee_id=1
        )
        pair_b = MagicMock(
            spec=MentorshipPairsEntity, pair_id=88, mentor_id=3, mentee_id=1
        )
        # Both deletions are in round_id=1, so both calls to
        # get_pairs_by_user_and_round resolve from this same pair list; this
        # method's own filtering (partner_id in (mentor_id, mentee_id)) is
        # what picks the right one per deletion.
        self.mock_pairs_repo.get_pairs_by_user_and_round.return_value = [pair_a, pair_b]

        def get_meetings_by_pair_side_effect(session, pair_id):
            if pair_id == 77:
                return [
                    MagicMock(
                        spec=MentorshipMeetingEntity,
                        meeting_id="abc",
                        source=MeetingSource.GOOGLE,
                    )
                ]
            if pair_id == 88:
                return [
                    MagicMock(
                        spec=MentorshipMeetingEntity,
                        meeting_id="def",
                        source=MeetingSource.GOOGLE,
                    ),
                    MagicMock(
                        spec=MentorshipMeetingEntity,
                        meeting_id="ghi",
                        source=MeetingSource.GOOGLE,
                    ),
                ]
            return []

        self.mock_meeting_repo.get_meetings_by_pair.side_effect = (
            get_meetings_by_pair_side_effect
        )
        # Everything succeeds on the Calendar side -- this test is purely
        # about the DB-side regrouping, not partial failure (see the
        # dedicated partial-success test below).
        self.mock_meeting_scheduling_service.cancel.return_value = (
            ["abc", "def", "ghi"],
            [],
        )
        self.mock_meeting_repo.recalculate_completed_count.return_value = 1

        await self.service.delete_google_meetings(
            session=self.mock_session,
            user_context=self.user_context,
            deletions=[
                {"round_id": 1, "partner_id": 2, "meeting_ids": ["abc"]},
                {"round_id": 1, "partner_id": 3, "meeting_ids": ["def", "ghi"]},
            ],
        )

        # Load-bearing: if the code instead passed the union of all
        # succeeded ids to every pair, this call would be
        # meeting_ids=["abc", "def", "ghi"] instead of just ["abc"], and
        # assert_any_call would fail to find it.
        self.mock_meeting_repo.delete_meetings.assert_any_call(
            session=self.mock_session, pair_id=77, meeting_ids=["abc"]
        )
        self.mock_meeting_repo.delete_meetings.assert_any_call(
            session=self.mock_session, pair_id=88, meeting_ids=["def", "ghi"]
        )
        self.assertEqual(self.mock_meeting_repo.delete_meetings.await_count, 2)

        self.mock_meeting_repo.recalculate_completed_count.assert_any_call(
            session=self.mock_session, pair_id=77
        )
        self.mock_meeting_repo.recalculate_completed_count.assert_any_call(
            session=self.mock_session, pair_id=88
        )
        self.assertEqual(
            self.mock_meeting_repo.recalculate_completed_count.await_count, 2
        )

    async def test_delete_google_meetings_partial_cancel_skips_failed_pair(self):
        """When Calendar cancels some ids but not others, only the succeeded
        ids may be deleted from the table, and a pair whose ids ALL failed
        must not have `recalculate_completed_count` called at all -- that
        pair's data never changed, so recomputing its count would be at best
        wasted work and at worst a race with a concurrent write."""
        pair_a = MagicMock(
            spec=MentorshipPairsEntity, pair_id=77, mentor_id=2, mentee_id=1
        )
        pair_b = MagicMock(
            spec=MentorshipPairsEntity, pair_id=88, mentor_id=3, mentee_id=1
        )
        self.mock_pairs_repo.get_pairs_by_user_and_round.return_value = [pair_a, pair_b]

        def get_meetings_by_pair_side_effect(session, pair_id):
            if pair_id == 77:
                return [
                    MagicMock(
                        spec=MentorshipMeetingEntity,
                        meeting_id="abc",
                        source=MeetingSource.GOOGLE,
                    )
                ]
            if pair_id == 88:
                return [
                    MagicMock(
                        spec=MentorshipMeetingEntity,
                        meeting_id="def",
                        source=MeetingSource.GOOGLE,
                    )
                ]
            return []

        self.mock_meeting_repo.get_meetings_by_pair.side_effect = (
            get_meetings_by_pair_side_effect
        )
        # "abc" (pair_a) succeeds; "def" (pair_b) fails outright.
        self.mock_meeting_scheduling_service.cancel.return_value = (["abc"], ["def"])
        self.mock_meeting_repo.recalculate_completed_count.return_value = 1

        result = await self.service.delete_google_meetings(
            session=self.mock_session,
            user_context=self.user_context,
            deletions=[
                {"round_id": 1, "partner_id": 2, "meeting_ids": ["abc"]},
                {"round_id": 1, "partner_id": 3, "meeting_ids": ["def"]},
            ],
        )

        # Load-bearing: if the code deleted failed ids too, this would
        # either be called with meeting_ids including "def", or called a
        # second time for pair_id=88 -- either way assert_called_once_with
        # below would fail.
        self.mock_meeting_repo.delete_meetings.assert_awaited_once_with(
            session=self.mock_session, pair_id=77, meeting_ids=["abc"]
        )
        self.mock_meeting_repo.recalculate_completed_count.assert_awaited_once_with(
            session=self.mock_session, pair_id=77
        )
        for call in self.mock_meeting_repo.recalculate_completed_count.await_args_list:
            self.assertNotEqual(call.kwargs.get("pair_id"), 88)

        self.assertEqual(result.succeeded_meeting_ids, ["abc"])
        self.assertEqual(result.failed_meeting_ids, ["def"])

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


class TestMeetingServiceReschedule(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.mock_logger = MagicMock()
        self.mock_users_repository = MagicMock()
        self.mock_users_repository.get_user_by_user_id = AsyncMock()
        self.mock_pairs_repo = MagicMock()
        self.mock_pairs_repo.get_pair_with_partner_by_round_and_users_and_status = (
            AsyncMock()
        )
        self.mock_session = AsyncMock()

        self.mock_meeting_scheduling_service = AsyncMock()
        self.mock_meeting_scheduling_service.update = AsyncMock(
            return_value={
                "google_event_id": "google-event-1",
                "meet_link": "https://meet.google.com/abc-def-ghi",
                "entry_points": [],
                "conference_id": "abc-def-ghi",
                "created": "",
            }
        )

        self.mock_meeting_repo = MagicMock()
        self.mock_meeting_repo.get_meetings_by_pair = AsyncMock()
        self.mock_meeting_repo.update_schedule = AsyncMock()

        self.service = MeetingService(
            logger=self.mock_logger,
            mentorship_pairs_repository=self.mock_pairs_repo,
            mentorship_mapper=MagicMock(),
            users_repository=self.mock_users_repository,
            meeting_scheduling_service=self.mock_meeting_scheduling_service,
            mentorship_calendar_id="cal-mentorship",
            mentorship_meeting_repository=self.mock_meeting_repo,
        )

        self.user_context = MagicMock(spec=UserContextDto, user_id=1)
        self.mock_current_user = MagicMock(user_id=1)
        self.mock_partner = MagicMock(user_id=2)
        self.mock_users_repository.get_user_by_user_id.return_value = (
            self.mock_current_user
        )
        self.mock_pair = MagicMock(pair_id=55)
        self.mock_pairs_repo.get_pair_with_partner_by_round_and_users_and_status.return_value = (
            self.mock_pair,
            self.mock_partner,
        )

        # Far future so the SCHEDULED gate passes on its own merits.
        self.scheduled_meeting = MagicMock(
            spec=MentorshipMeetingEntity,
            meeting_id="google-event-1",
            pair_id=55,
            source=MeetingSource.GOOGLE,
            start_datetime=datetime(2099, 5, 1, 10, 0, tzinfo=timezone.utc),
            end_datetime=datetime(2099, 5, 1, 10, 30, tzinfo=timezone.utc),
            is_completed=False,
            meet_link="https://meet.google.com/abc-def-ghi",
            entry_points=[],
        )
        self.mock_meeting_repo.get_meetings_by_pair.return_value = [
            self.scheduled_meeting
        ]

        self.kwargs = dict(
            session=self.mock_session,
            user_context=self.user_context,
            meeting_id="google-event-1",
            round_id=10,
            partner_id=2,
            timezone="America/New_York",
            start_date=date(2099, 6, 1),
            start_time="09:00",
            duration_minutes=60,
        )

    async def test_patches_calendar_and_moves_the_row(self):
        await self.service.reschedule_google_meeting(**self.kwargs)

        # 09:00 America/New_York on 2099-06-01 is 13:00Z (EDT, UTC-4).
        expected_start = datetime(2099, 6, 1, 13, 0, tzinfo=timezone.utc)
        expected_end = datetime(2099, 6, 1, 14, 0, tzinfo=timezone.utc)

        self.mock_meeting_scheduling_service.update.assert_awaited_once()
        call = self.mock_meeting_scheduling_service.update.await_args
        self.assertEqual(call.kwargs["event_id"], "google-event-1")
        self.assertEqual(call.kwargs["start_utc"], expected_start)
        self.assertEqual(call.kwargs["end_utc"], expected_end)
        self.assertEqual(sorted(call.kwargs["attendee_user_ids"]), [1, 2])
        self.assertEqual(call.kwargs["calendar_id"], "cal-mentorship")

        self.mock_meeting_repo.update_schedule.assert_awaited_once_with(
            session=self.mock_session,
            meeting=self.scheduled_meeting,
            start_datetime=expected_start,
            end_datetime=expected_end,
        )
        self.mock_session.commit.assert_awaited()

    async def test_rejects_when_no_active_pair(self):
        self.mock_pairs_repo.get_pair_with_partner_by_round_and_users_and_status.return_value = None
        with self.assertRaises(ValueError):
            await self.service.reschedule_google_meeting(**self.kwargs)
        self.mock_meeting_scheduling_service.update.assert_not_awaited()

    async def test_rejects_a_meeting_that_is_not_this_pairs(self):
        # The id exists on Calendar but belongs to some other pair: the row
        # lookup is what stops it being moved from here.
        self.mock_meeting_repo.get_meetings_by_pair.return_value = []
        with self.assertRaises(ValueError):
            await self.service.reschedule_google_meeting(**self.kwargs)
        self.mock_meeting_scheduling_service.update.assert_not_awaited()

    async def test_rejects_a_manually_logged_meeting(self):
        self.scheduled_meeting.source = MeetingSource.MANUAL
        with self.assertRaises(ValueError):
            await self.service.reschedule_google_meeting(**self.kwargs)
        self.mock_meeting_scheduling_service.update.assert_not_awaited()

    async def test_rejects_a_completed_meeting(self):
        self.scheduled_meeting.is_completed = True
        with self.assertRaises(ValueError):
            await self.service.reschedule_google_meeting(**self.kwargs)
        self.mock_meeting_scheduling_service.update.assert_not_awaited()

    async def test_rejects_a_meeting_whose_slot_has_passed(self):
        # Not completed but already started: history the attendance sweep
        # never closed out, not something to move.
        self.scheduled_meeting.start_datetime = datetime(
            2020, 1, 1, tzinfo=timezone.utc
        )
        with self.assertRaises(ValueError):
            await self.service.reschedule_google_meeting(**self.kwargs)
        self.mock_meeting_scheduling_service.update.assert_not_awaited()

    async def test_converts_a_vanished_calendar_event_into_a_recoverable_error(self):
        self.mock_meeting_scheduling_service.update.side_effect = MeetingGoneError(
            "gone"
        )
        with self.assertRaises(ValueError) as ctx:
            await self.service.reschedule_google_meeting(**self.kwargs)
        self.assertIn("no longer exists", str(ctx.exception))
        self.mock_meeting_repo.update_schedule.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
