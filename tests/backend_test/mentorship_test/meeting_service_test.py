import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, AsyncMock, patch

from backend.mentorship.meeting_service import MeetingService
from backend.dto.user_context_dto import UserContextDto
from backend.dto.meeting_dto import MeetingDto
from backend.dto.meeting_create_dto import MeetingCreateDto
from backend.dto.google_meeting_response_detail_dto import (
    GoogleMeetingResponseDetailDto,
)
from backend.entity.users_entity import UsersEntity
from backend.entity.mentorship_pairs_entity import MentorshipPairsEntity
from backend.common.mentorship_enums import UserTimezone, PairStatus
from backend.common.user_role import UserRole


class TestMeetingServiceV1(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.mock_logger = MagicMock()
        self.mock_pairs_repo = MagicMock()
        self.mock_pairs_repo.get_pairs_by_user_and_round = AsyncMock()
        self.mock_pairs_repo.get_pair_by_mentee_and_round = AsyncMock()
        self.mock_pairs_repo.upsert_pairs = AsyncMock()

        self.mock_mapper = MagicMock()
        self.mock_identity_service = MagicMock()
        self.mock_identity_service.get_user = AsyncMock()
        self.mock_session = AsyncMock()

        self.mock_google_service = MagicMock()

        self.meeting_service = MeetingService(
            logger=self.mock_logger,
            mentorship_pairs_repository=self.mock_pairs_repo,
            mentorship_mapper=self.mock_mapper,
            user_identity_service=self.mock_identity_service,
            google_service=self.mock_google_service,
        )

        self.user_id = 1
        self.round_id = 10
        self.partner_id = 100
        self.user_context = MagicMock(spec=UserContextDto, sub="sub-123")
        self.mock_current_user = MagicMock(spec=UsersEntity, user_id=self.user_id)
        self.mock_current_user.timezone = UserTimezone.AMERICA_NEW_YORK
        self.mock_identity_service.get_user.return_value = (
            self.mock_current_user,
            False,
        )

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
        self.assertEqual(result.user_timezone, UserTimezone.AMERICA_NEW_YORK)
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
        self.assertEqual(len(self.mock_pair_entity.meeting_log["meeting_time_list"]), 2)
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


class TestMeetingServiceV2(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.mock_logger = MagicMock()
        self.mock_user_identity_service = MagicMock()
        self.mock_user_identity_service.get_user = AsyncMock()
        self.mock_google_service = MagicMock()
        self.mock_mentorship_pairs_repository = MagicMock()
        self.mock_mentorship_pairs_repository.get_pair_with_partner_by_round_and_users_and_status = AsyncMock()
        self.mock_mentorship_pairs_repository.append_google_meeting = AsyncMock()

        self.mock_session = AsyncMock()

        self.service = MeetingService(
            logger=self.mock_logger,
            mentorship_pairs_repository=self.mock_mentorship_pairs_repository,
            mentorship_mapper=MagicMock(),
            user_identity_service=self.mock_user_identity_service,
            google_service=self.mock_google_service,
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

        self.mock_user_identity_service.get_user.return_value = (
            self.mock_current_user,
            None,
        )

        self.google_result = {
            "id": "google_event_123",
            "hangoutLink": "https://meet.google.com/abc-def-ghi",
            "conferenceData": {
                "entryPoints": [
                    {
                        "entryPointType": "video",
                        "uri": "https://meet.google.com/abc-def-ghi",
                    }
                ],
                "conferenceId": "abc-def-ghi",
            },
        }
        self.mock_google_service.insert_google_meeting.return_value = self.google_result
        self.mock_google_service.get_meet_space_name = AsyncMock(
            return_value="spaces/INTERNALID123"
        )
        self.mock_google_service.update_meet_space_type_to_open = AsyncMock()

        self.mock_pair = MagicMock()
        self.mock_pair.meeting_log = None
        self.mock_mentorship_pairs_repository.get_pair_with_partner_by_round_and_users_and_status.return_value = (
            self.mock_pair,
            self.mock_partner,
        )

        self.user_context = MagicMock(spec=UserContextDto)
        self.start_dt = datetime(2026, 3, 20, 10, 0, tzinfo=timezone.utc)
        self.end_dt = datetime(2026, 3, 20, 11, 0, tzinfo=timezone.utc)

        self.mock_pairs_repo = self.mock_mentorship_pairs_repository
        self.mock_pairs_repo.get_pairs_by_user_and_round = AsyncMock()

        self.mock_mapper = MagicMock()

        self.meeting_service = MeetingService(
            logger=self.mock_logger,
            mentorship_pairs_repository=self.mock_pairs_repo,
            mentorship_mapper=self.mock_mapper,
            user_identity_service=self.mock_user_identity_service,
            google_service=self.mock_google_service,
        )

        self.user_id = 1
        self.round_id = 10
        self.partner_id = 100

        self.mock_current_user.timezone = UserTimezone.AMERICA_NEW_YORK

        self.user_context.roles = [UserRole.MENTORSHIP]

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

        self.mock_user_identity_service.get_user.return_value = (
            self.mock_current_user,
            False,
        )

    @patch("backend.mentorship.meeting_service.uuid")
    async def test_create_google_meeting_success(self, mock_uuid):
        """Test successful meeting creation with correct response fields."""
        mock_uuid.uuid4.return_value = MagicMock(
            hex="abcdef1234567890abcdef1234567890",
            __str__=lambda _: "abcdef12-3456-7890-abcd-ef1234567890",
        )

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

    @patch("backend.mentorship.meeting_service.uuid")
    async def test_create_google_meeting_calls_google_api_with_correct_args(
        self, mock_uuid
    ):
        """Test that Google Calendar API is called with correct summary and attendees."""
        mock_uuid.uuid4.return_value = MagicMock(
            hex="abcdef1234567890abcdef1234567890",
            __str__=lambda _: "request-id-123",
        )

        await self.service.create_google_meeting(
            session=self.mock_session,
            user_context=self.user_context,
            partner_id=2,
            round_id=1,
            start_datetime=self.start_dt,
            end_datetime=self.end_dt,
        )

        self.mock_google_service.insert_google_meeting.assert_called_once_with(
            summary="Circlecat Mentorship - Alice / Bob",
            start_time=self.start_dt,
            end_time=self.end_dt,
            attendees_emails=["alice@example.com", "bob@example.com"],
            request_id="request-id-123",
            event_id="abcdef1234567890abcdef1234567890",
        )

    @patch("backend.mentorship.meeting_service.uuid")
    async def test_create_google_meeting_persists_meeting_log(self, mock_uuid):
        """Test that meeting result is persisted to meeting_log."""
        mock_uuid.uuid4.return_value = MagicMock(
            hex="abcdef1234567890abcdef1234567890",
            __str__=lambda _: "request-id-123",
        )

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
        self.mock_google_service.insert_google_meeting.assert_not_called()

    @patch("backend.mentorship.meeting_service.uuid")
    async def test_create_google_meeting_sets_meet_space_to_open(self, mock_uuid):
        """Test that get_meet_space_name and update_meet_space_type_to_open are called with conferenceId."""
        mock_uuid.uuid4.return_value = MagicMock(
            hex="abcdef1234567890abcdef1234567890",
            __str__=lambda _: "request-id-123",
        )

        await self.service.create_google_meeting(
            session=self.mock_session,
            user_context=self.user_context,
            partner_id=2,
            round_id=1,
            start_datetime=self.start_dt,
            end_datetime=self.end_dt,
        )

        self.mock_google_service.get_meet_space_name.assert_awaited_once_with(
            "abc-def-ghi"
        )
        self.mock_google_service.update_meet_space_type_to_open.assert_awaited_once_with(
            "spaces/INTERNALID123"
        )

    @patch("backend.mentorship.meeting_service.uuid")
    async def test_create_google_meeting_meet_update_failure_is_non_fatal(
        self, mock_uuid
    ):
        """Test that a failure in update_meet_space_type_to_open does not block the response."""
        mock_uuid.uuid4.return_value = MagicMock(
            hex="abcdef1234567890abcdef1234567890",
            __str__=lambda _: "request-id-123",
        )
        self.mock_google_service.get_meet_space_name.side_effect = RuntimeError(
            "Meet API down"
        )

        result = await self.service.create_google_meeting(
            session=self.mock_session,
            user_context=self.user_context,
            partner_id=2,
            round_id=1,
            start_datetime=self.start_dt,
            end_datetime=self.end_dt,
        )

        self.assertIsInstance(result, GoogleMeetingResponseDetailDto)
        self.mock_logger.warning.assert_called_once()
        self.mock_google_service.update_meet_space_type_to_open.assert_not_awaited()

    @patch("backend.mentorship.meeting_service.uuid")
    async def test_create_google_meeting_skips_meet_update_when_no_conference_id(
        self, mock_uuid
    ):
        """Test that Meet space update is skipped when conferenceId is missing from response."""
        mock_uuid.uuid4.return_value = MagicMock(
            hex="abcdef1234567890abcdef1234567890",
            __str__=lambda _: "request-id-123",
        )
        self.mock_google_service.insert_google_meeting.return_value = {
            "id": "google_event_123",
            "hangoutLink": "https://meet.google.com/abc-def-ghi",
            "conferenceData": {},
        }

        await self.service.create_google_meeting(
            session=self.mock_session,
            user_context=self.user_context,
            partner_id=2,
            round_id=1,
            start_datetime=self.start_dt,
            end_datetime=self.end_dt,
        )

        self.mock_google_service.get_meet_space_name.assert_not_awaited()
        self.mock_google_service.update_meet_space_type_to_open.assert_not_awaited()

    @patch("backend.mentorship.meeting_service.uuid")
    async def test_create_google_meeting_uses_first_name_when_no_preferred_name(
        self, mock_uuid
    ):
        """Test fallback to first_name when preferred_name is None."""
        mock_uuid.uuid4.return_value = MagicMock(
            hex="abcdef1234567890abcdef1234567890",
            __str__=lambda _: "request-id-123",
        )
        self.mock_current_user.preferred_name = None
        self.mock_current_user.first_name = "AliceFirst"
        self.mock_partner.preferred_name = None
        self.mock_partner.first_name = "BobFirst"

        await self.service.create_google_meeting(
            session=self.mock_session,
            user_context=self.user_context,
            partner_id=2,
            round_id=1,
            start_datetime=self.start_dt,
            end_datetime=self.end_dt,
        )

        call_kwargs = self.mock_google_service.insert_google_meeting.call_args.kwargs
        self.assertEqual(
            call_kwargs["summary"],
            "Circlecat Mentorship - AliceFirst / BobFirst",
        )

    async def test_get_meetings_by_user_and_round_v2_success(self):
        """Test retrieved and mapped meeting logs for a matched user correctly in v2."""
        self.mock_pairs_repo.get_pairs_by_user_and_round.return_value = [
            self.mock_pair_entity
        ]

        self.user_context.roles = [UserRole.MENTORSHIP_ADMIN]
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

    async def test_get_meetings_by_user_and_round_v2_no_pair_found(self):
        """Verify that an empty MeetingDto is returned when no mentorship pairs exist in v2."""
        self.user_context.roles = [UserRole.MENTORSHIP]
        self.mock_pairs_repo.get_pairs_by_user_and_round.return_value = []

        result = await self.meeting_service.get_meetings_by_user_and_round_v2(
            self.mock_session,
            self.user_context,
            self.round_id,
            include_details=False,
        )

        self.assertIsInstance(result, MeetingDto)
        self.assertEqual(result.round_id, self.round_id)
        self.assertEqual(result.user_timezone, UserTimezone.AMERICA_NEW_YORK)
        self.assertEqual(len(result.meeting_info), 0)

        self.mock_mapper.map_to_meeting_v2_dto.assert_not_called()

    async def test_get_meetings_by_user_and_round_v2_non_admin_detail_not_allowed(self):
        """Verify detail fields are not allowed for non-admin users even when include_details=True."""
        self.mock_pairs_repo.get_pairs_by_user_and_round.return_value = [
            self.mock_pair_entity
        ]
        self.user_context.roles = [UserRole.MENTORSHIP]

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


if __name__ == "__main__":
    unittest.main()
