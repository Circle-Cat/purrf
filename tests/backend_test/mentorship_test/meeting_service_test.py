import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, AsyncMock

from backend.mentorship.meeting_service import MeetingService
from backend.dto.user_context_dto import UserContextDto
from backend.dto.meeting_dto import MeetingDto
from backend.dto.meeting_create_dto import MeetingCreateDto
from backend.entity.users_entity import UsersEntity
from backend.entity.mentorship_pairs_entity import MentorshipPairsEntity
from backend.common.mentorship_enums import UserTimezone


class TestMeetingService(unittest.IsolatedAsyncioTestCase):
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

        self.meeting_service = MeetingService(
            logger=self.mock_logger,
            mentorship_pairs_repository=self.mock_pairs_repo,
            mentorship_mapper=self.mock_mapper,
            user_identity_service=self.mock_identity_service,
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


if __name__ == "__main__":
    unittest.main()
