import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, AsyncMock
from backend.mentorship.rounds_service import RoundsService
from backend.dto.rounds_dto import RoundsDto
from backend.dto.rounds_create_dto import TimelineCreateDto
from backend.dto.rounds_create_dto import RoundsCreateDto
from backend.entity.mentorship_round_entity import MentorshipRoundEntity
from backend.mentorship.mentorship_mapper import MentorshipMapper


class TestRoundsService(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.mock_repo = MagicMock()
        self.mock_repo.get_all_rounds = AsyncMock()
        self.mock_repo.get_by_round_id = AsyncMock()
        self.mock_repo.upsert_round = AsyncMock()

        self.mock_pairs_repo = MagicMock()
        self.mock_pairs_repo.get_pair_stats = AsyncMock()

        self.mock_mapper = MagicMock()
        self.mock_session = AsyncMock()

        self.service = RoundsService(
            mentorship_round_repository=self.mock_repo,
            mentorship_mapper=self.mock_mapper,
            mentorship_pairs_repository=self.mock_pairs_repo,
        )

        self.timeline_data = TimelineCreateDto(
            promotion_start_at=datetime(2025, 12, 2, 7, 59, 59, tzinfo=timezone.utc),
            mentor_application_deadline_at=datetime(
                2026, 1, 16, 7, 59, 59, tzinfo=timezone.utc
            ),
            mentee_application_deadline_at=datetime(
                2026, 1, 18, 7, 59, 59, tzinfo=timezone.utc
            ),
            onboarding_deadline_at=datetime(
                2026, 1, 25, 7, 59, 59, tzinfo=timezone.utc
            ),
            match_notification_at=datetime(2026, 2, 3, 7, 59, 59, tzinfo=timezone.utc),
            meetings_completion_deadline_at=datetime(
                2026, 5, 26, 6, 59, 59, tzinfo=timezone.utc
            ),
            feedback_deadline_at=datetime(2026, 6, 11, 6, 59, 59, tzinfo=timezone.utc),
        )

    def _use_real_mapper(self):
        """upsert_rounds builds its response through the mapper; a real one
        makes the response reflect what was written onto the entity."""
        self.service.mentorship_mapper = MentorshipMapper()

    def _assert_timeline_written(self, entity, timeline: TimelineCreateDto):
        for field in timeline.model_fields_set:
            self.assertEqual(
                getattr(entity, field), getattr(timeline, field), msg=field
            )

    async def test_get_all_rounds_with_details(self):
        """Test get all rounds with participant and meeting counts."""
        mock_mentorship_round_entities = [MagicMock(spec=MentorshipRoundEntity)]
        mock_rounds_dtos = [MagicMock(spec=RoundsDto)]
        mock_pair_stats = {
            1: {
                "active_pairs": 9,
                "matched_participants": 18,
                "total_completed_meetings": 45,
            },
            2: {
                "active_pairs": 5,
                "matched_participants": 10,
                "total_completed_meetings": 28,
            },
        }

        self.mock_repo.get_all_rounds.return_value = mock_mentorship_round_entities
        self.mock_pairs_repo.get_pair_stats.return_value = mock_pair_stats
        self.mock_mapper.map_to_rounds_dto.return_value = mock_rounds_dtos

        result = await self.service.get_all_rounds(
            self.mock_session, include_details=True
        )

        self.mock_repo.get_all_rounds.assert_awaited_once_with(self.mock_session)
        self.mock_pairs_repo.get_pair_stats.assert_awaited_once_with(self.mock_session)
        self.mock_mapper.map_to_rounds_dto.assert_called_once_with(
            mock_mentorship_round_entities,
            mock_pair_stats,
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

    async def test_get_all_rounds_skips_detail_queries(self):
        """Test round stats are not fetched when include_details is False."""
        mock_entities = [MagicMock(spec=MentorshipRoundEntity)]
        self.mock_repo.get_all_rounds.return_value = mock_entities
        self.mock_mapper.map_to_rounds_dto.return_value = []

        await self.service.get_all_rounds(self.mock_session, include_details=False)

        self.mock_pairs_repo.get_pair_stats.assert_not_awaited()

    async def test_upsert_rounds_create(self):
        """Test creating a new round writes each timeline date onto its own
        column and returns a DTO read back from the stored entity."""
        self._use_real_mapper()
        new_round = RoundsCreateDto(
            name="2026-spring",
            mentee_average_score=4.5,
            mentor_average_score=5.0,
            expectations="Expectations text",
            timeline=self.timeline_data,
            required_meetings=5,
        )

        async def assign_id(session, entity):
            entity.round_id = 1
            return entity

        self.mock_repo.upsert_round = AsyncMock(side_effect=assign_id)

        result = await self.service.upsert_rounds(self.mock_session, new_round)

        stored = self.mock_repo.upsert_round.await_args.args[1]
        self._assert_timeline_written(stored, self.timeline_data)
        self.assertIsNone(stored.description)
        self.assertIsNone(stored.onboarding_notification_at)
        self.mock_session.commit.assert_awaited_once()

        self.assertEqual(result.id, 1)
        self.assertEqual(result.name, "2026-spring")
        self.assertEqual(result.mentee_average_score, 4.5)
        self.assertEqual(result.mentor_average_score, 5.0)
        self.assertEqual(result.expectations, "Expectations text")
        self.assertEqual(result.required_meetings, 5)
        self.assertEqual(
            result.timeline.onboarding_deadline_at,
            self.timeline_data.onboarding_deadline_at,
        )
        self.assertEqual(
            result.timeline.mentee_application_deadline_at,
            self.timeline_data.mentee_application_deadline_at,
        )
        self.assertEqual(
            result.timeline.feedback_deadline_at,
            self.timeline_data.feedback_deadline_at,
        )

    async def test_upsert_rounds_update(self):
        """Test updating an existing round: an omitted optional date keeps
        its stored value, an explicit null clears it, and the response is
        read from the entity rather than echoed from the request."""
        self._use_real_mapper()
        stored_feedback_start = datetime(2026, 6, 1, 0, 0, 0, tzinfo=timezone.utc)
        existing_round = MentorshipRoundEntity(
            round_id=1,
            name="Existing Round",
            mentee_average_score=3.5,
            mentor_average_score=4.0,
            expectations="Old expectations",
            required_meetings=5,
            promotion_start_at=datetime(2025, 11, 1, tzinfo=timezone.utc),
            mentor_application_deadline_at=datetime(2025, 12, 1, tzinfo=timezone.utc),
            mentee_application_deadline_at=datetime(2025, 12, 3, tzinfo=timezone.utc),
            onboarding_deadline_at=datetime(2025, 12, 10, tzinfo=timezone.utc),
            match_notification_at=datetime(2026, 1, 5, tzinfo=timezone.utc),
            meetings_completion_deadline_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
            meeting_log_reminder_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
            feedback_start_at=stored_feedback_start,
            feedback_deadline_at=datetime(2026, 6, 20, tzinfo=timezone.utc),
        )
        self.mock_repo.get_by_round_id.return_value = existing_round
        self.mock_repo.upsert_round = AsyncMock(
            side_effect=lambda session, entity: entity
        )

        timeline = self.timeline_data.model_copy()
        timeline.meeting_log_reminder_at = None
        self.assertNotIn("feedback_start_at", timeline.model_fields_set)
        updated_round = RoundsCreateDto(
            id=1,
            name="Updated Round",
            mentee_average_score=4.0,
            mentor_average_score=4.8,
            expectations="Updated expectations",
            timeline=timeline,
            required_meetings=3,
        )

        result = await self.service.upsert_rounds(self.mock_session, updated_round)

        self.mock_repo.upsert_round.assert_awaited_once_with(
            self.mock_session, existing_round
        )
        self._assert_timeline_written(existing_round, timeline)
        self.assertEqual(existing_round.feedback_start_at, stored_feedback_start)
        self.assertIsNone(existing_round.meeting_log_reminder_at)

        self.assertEqual(result.id, 1)
        self.assertEqual(result.name, "Updated Round")
        self.assertEqual(result.mentee_average_score, 4.0)
        self.assertEqual(result.mentor_average_score, 4.8)
        self.assertEqual(result.expectations, "Updated expectations")
        self.assertEqual(result.required_meetings, 3)
        self.assertEqual(result.timeline.feedback_start_at, stored_feedback_start)
        self.assertIsNone(result.timeline.meeting_log_reminder_at)
        self.assertEqual(
            result.timeline.onboarding_deadline_at, timeline.onboarding_deadline_at
        )

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
