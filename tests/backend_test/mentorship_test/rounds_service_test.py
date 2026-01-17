import unittest
from datetime import date
from unittest.mock import MagicMock, AsyncMock
from backend.mentorship.rounds_service import RoundsService
from backend.dto.rounds_dto import RoundsDto
from backend.dto.rounds_create_dto import TimelineCreateDto
from backend.dto.rounds_create_dto import RoundsCreateDto
from backend.entity.mentorship_round_entity import MentorshipRoundEntity


class TestRoundsService(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.mock_repo = MagicMock()
        self.mock_repo.get_all_rounds = AsyncMock()
        self.mock_repo.get_by_round_id = AsyncMock()
        self.mock_repo.upsert_round = AsyncMock()

        self.mock_mapper = MagicMock()
        self.mock_session = AsyncMock()

        self.service = RoundsService(
            mentorship_round_repository=self.mock_repo,
            mentorship_mapper=self.mock_mapper,
        )

        self.timeline_data = TimelineCreateDto(
            promotion_start_at=date(2025, 12, 1),
            application_deadline_at=date(2026, 1, 15),
            review_start_at=date(2026, 1, 16),
            acceptance_notification_at=date(2026, 1, 25),
            matching_completed_at=date(2026, 1, 31),
            match_notification_at=date(2026, 2, 2),
            first_meeting_deadline_at=date(2026, 2, 25),
            meetings_completion_deadline_at=date(2026, 5, 25),
            feedback_deadline_at=date(2026, 6, 10),
        )

    def _timeline_to_dict(self, timeline: TimelineCreateDto) -> dict:
        """Help to convert timeline to dict format."""
        return {
            "promotion_start_at": timeline.promotion_start_at.isoformat(),
            "application_deadline_at": timeline.application_deadline_at.isoformat(),
            "review_start_at": timeline.review_start_at.isoformat(),
            "acceptance_notification_at": timeline.acceptance_notification_at.isoformat(),
            "matching_completed_at": timeline.matching_completed_at.isoformat(),
            "match_notification_at": timeline.match_notification_at.isoformat(),
            "first_meeting_deadline_at": timeline.first_meeting_deadline_at.isoformat(),
            "meetings_completion_deadline_at": timeline.meetings_completion_deadline_at.isoformat(),
            "feedback_deadline_at": timeline.feedback_deadline_at.isoformat(),
        }

    async def test_get_all_rounds(self):
        """Test retrieving and mapping of all mentorship rounds."""
        mock_mentorship_round_entities = [MagicMock(spec=MentorshipRoundEntity)]
        mock_rounds_dtos = [MagicMock(spec=RoundsDto)]

        self.mock_repo.get_all_rounds.return_value = mock_mentorship_round_entities
        self.mock_mapper.map_to_rounds_dto.return_value = mock_rounds_dtos

        result = await self.service.get_all_rounds(self.mock_session)

        self.mock_repo.get_all_rounds.assert_awaited_once_with(self.mock_session)
        self.mock_mapper.map_to_rounds_dto.assert_called_once_with(
            mock_mentorship_round_entities
        )

        self.assertEqual(result, mock_rounds_dtos)

    async def test_get_all_rounds_empty(self):
        """Test return an empty list when no rounds exist."""
        self.mock_repo.get_all_rounds.return_value = []
        self.mock_mapper.map_to_rounds_dto.return_value = []

        result = await self.service.get_all_rounds(self.mock_session)

        self.assertEqual(result, [])
        self.mock_repo.get_all_rounds.assert_awaited_once_with(self.mock_session)
        self.mock_mapper.map_to_rounds_dto.assert_called_once_with([])

    async def test_upsert_rounds_create(self):
        """Test creating a new mentorship round."""
        new_round = RoundsCreateDto(
            name="2026-spring",
            mentee_average_score=4.5,
            mentor_average_score=5.0,
            expectations="Expectations text",
            timeline=self.timeline_data,
            required_meetings=5,
        )

        mock_entity = MentorshipRoundEntity(
            round_id=1,
            name=new_round.name,
            mentee_average_score=new_round.mentee_average_score,
            mentor_average_score=new_round.mentor_average_score,
            expectations=new_round.expectations,
            description=new_round.timeline.to_db_dict(),
            required_meetings=new_round.required_meetings,
        )

        self.mock_repo.upsert_round = AsyncMock(return_value=mock_entity)

        result = await self.service.upsert_rounds(self.mock_session, new_round)

        self.assertIsNotNone(result)
        self.assertEqual(result.id, mock_entity.round_id)
        self.assertEqual(result.name, mock_entity.name)
        self.assertEqual(result.mentee_average_score, mock_entity.mentee_average_score)
        self.assertEqual(result.mentor_average_score, mock_entity.mentor_average_score)
        self.assertEqual(result.expectations, mock_entity.expectations)
        self.assertEqual(
            self._timeline_to_dict(result.timeline), mock_entity.description
        )
        self.assertEqual(result.required_meetings, mock_entity.required_meetings)

    async def test_upsert_rounds_update(self):
        """Test updating an existing mentorship round."""

        updated_round = RoundsCreateDto(
            id=1,
            name="Updated Round",
            mentee_average_score=4.0,
            mentor_average_score=4.8,
            expectations="Updated expectations",
            timeline=self.timeline_data,
            required_meetings=3,
        )

        existing_round = MentorshipRoundEntity(
            round_id=1,
            name="Existing Round",
            mentee_average_score=3.5,
            mentor_average_score=4.0,
            expectations="Old expectations",
            description={"goal": "improving skills"},
            required_meetings=5,
        )

        self.mock_repo.get_by_round_id.return_value = existing_round

        updated_entity = MentorshipRoundEntity(
            round_id=existing_round.round_id,
            name=updated_round.name,
            mentee_average_score=updated_round.mentee_average_score,
            mentor_average_score=updated_round.mentor_average_score,
            expectations=updated_round.expectations,
            description=updated_round.timeline.to_db_dict(),
            required_meetings=updated_round.required_meetings,
        )

        self.mock_repo.upsert_round = AsyncMock(return_value=updated_entity)

        result = await self.service.upsert_rounds(self.mock_session, updated_round)

        self.assertIsNotNone(result)
        self.assertEqual(result.id, existing_round.round_id)
        self.assertEqual(result.name, "Updated Round")
        self.assertEqual(result.mentee_average_score, 4.0)
        self.assertEqual(result.mentor_average_score, 4.8)
        self.assertEqual(result.expectations, "Updated expectations")
        self.assertEqual(
            self._timeline_to_dict(result.timeline), updated_entity.description
        )
        self.assertEqual(result.required_meetings, 3)

    async def test_upsert_rounds_not_found(self):
        """Test handling of updating a non-existent mentorship round."""
        not_found_round = RoundsCreateDto(
            id=999,
            name="Non-existent Round",
            mentee_average_score=4.5,
            mentor_average_score=5.0,
            expectations="Expectations text",
            timeline=self.timeline_data,
            required_meetings=5,
        )

        self.mock_repo.get_by_round_id = AsyncMock(return_value=None)

        with self.assertRaises(ValueError, msg="Round with given ID does not exist."):
            await self.service.upsert_rounds(self.mock_session, not_found_round)


if __name__ == "__main__":
    unittest.main()
