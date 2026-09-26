import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, AsyncMock, patch
from pydantic import ValidationError
from backend.mentorship.rounds_service import RoundsService
from backend.dto.rounds_dto import RoundSlotsDto, RoundsDto
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
        self.assertIsNone(result.mentee_average_score)
        self.assertIsNone(result.mentor_average_score)
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
        # Saving the round keeps the averages feedback produced.
        self.assertEqual(existing_round.mentee_average_score, 3.5)
        self.assertEqual(existing_round.mentor_average_score, 4.0)
        self.assertEqual(result.mentee_average_score, 3.5)
        self.assertEqual(result.mentor_average_score, 4.0)
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
            expectations="Expectations text",
            timeline=self.timeline_data,
            required_meetings=5,
        )

        self.mock_repo.get_by_round_id = AsyncMock(return_value=None)

        with self.assertRaises(ValueError, msg="Round with given ID does not exist."):
            await self.service.upsert_rounds(self.mock_session, not_found_round)

    def test_round_request_cannot_carry_average_scores(self):
        """The averages are derived from feedback, so a request naming one
        is rejected rather than silently written."""
        for field in ("mentee_average_score", "mentor_average_score"):
            with self.subTest(field=field), self.assertRaises(ValidationError):
                RoundsCreateDto(
                    name="2026-spring",
                    timeline=self.timeline_data,
                    required_meetings=5,
                    **{field: 4.5},
                )


class TestGetRoundSlots(unittest.IsolatedAsyncioTestCase):
    """get_round_slots assembles the dashboard's slots at one server instant."""

    NOW = datetime(2026, 8, 15, 12, 0, tzinfo=timezone.utc)
    MICRO = timedelta(microseconds=1)

    async def asyncSetUp(self):
        self.mock_repo = MagicMock()
        self.mock_repo.get_open_registration_round = AsyncMock(return_value=None)
        self.mock_repo.get_latest_promoted_round = AsyncMock(return_value=None)
        self.mock_repo.get_all_rounds = AsyncMock(return_value=[])
        self.mock_session = AsyncMock()

        self.service = RoundsService(
            mentorship_round_repository=self.mock_repo,
            mentorship_mapper=MentorshipMapper(),
            mentorship_pairs_repository=MagicMock(),
        )

        self.datetime_patcher = patch("backend.mentorship.rounds_service.datetime")
        mock_dt = self.datetime_patcher.start()
        mock_dt.now.return_value = self.NOW

    async def asyncTearDown(self):
        self.datetime_patcher.stop()

    def _round(self, round_id, name=None, **dates) -> MentorshipRoundEntity:
        fields = dict(
            round_id=round_id,
            name=name or f"round-{round_id}",
            required_meetings=5,
            onboarding_deadline_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
        )
        fields.update(dates)
        return MentorshipRoundEntity(**fields)

    async def _slots(self) -> RoundSlotsDto:
        return await self.service.get_round_slots(self.mock_session)

    async def test_open_round_is_the_registration_round(self):
        open_round = self._round(
            11,
            "2026 Fall",
            promotion_start_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
            onboarding_deadline_at=datetime(2026, 8, 31, tzinfo=timezone.utc),
            match_notification_at=datetime(2026, 9, 10, tzinfo=timezone.utc),
            feedback_deadline_at=datetime(2027, 1, 15, tzinfo=timezone.utc),
        )
        self.mock_repo.get_open_registration_round.return_value = open_round
        self.mock_repo.get_latest_promoted_round.return_value = self._round(
            12,
            "2027 Spring",
            promotion_start_at=datetime(2026, 8, 10, tzinfo=timezone.utc),
            onboarding_deadline_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
        )

        slots = await self._slots()

        self.assertEqual(slots.registration_round_id, 11)
        self.assertEqual(slots.registration_round_name, "2026 Fall")
        self.assertEqual(
            slots.registration_deadline_at,
            datetime(2026, 8, 31, tzinfo=timezone.utc),
        )
        self.assertTrue(slots.is_registration_open)
        self.assertFalse(slots.can_view_match)
        self.mock_repo.get_open_registration_round.assert_awaited_once_with(
            self.mock_session, self.NOW
        )

    async def test_falls_back_to_the_latest_promoted_round_when_none_is_open(self):
        self.mock_repo.get_latest_promoted_round.return_value = self._round(
            12,
            "2026 Summer",
            promotion_start_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
            onboarding_deadline_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
        )

        slots = await self._slots()

        self.assertEqual(slots.registration_round_id, 12)
        self.assertEqual(slots.registration_round_name, "2026 Summer")
        self.assertEqual(
            slots.registration_deadline_at,
            datetime(2026, 6, 1, tzinfo=timezone.utc),
        )
        self.assertFalse(slots.is_registration_open)
        self.mock_repo.get_latest_promoted_round.assert_awaited_once_with(
            self.mock_session, self.NOW
        )

    async def test_no_rounds_at_all(self):
        slots = await self._slots()

        self.assertEqual(slots, RoundSlotsDto())
        self.assertIsNone(slots.registration_round_id)
        self.assertIsNone(slots.registration_round_name)
        self.assertIsNone(slots.registration_deadline_at)
        self.assertFalse(slots.is_registration_open)
        self.assertFalse(slots.can_view_match)
        self.assertFalse(slots.is_feedback_enabled)
        self.assertIsNone(slots.active_round_id)

    async def test_can_view_match_only_inside_the_registration_rounds_window(self):
        match_at = datetime(2026, 8, 1, tzinfo=timezone.utc)
        feedback_at = datetime(2026, 12, 1, tzinfo=timezone.utc)
        cases = (
            ("on match notification", match_at, feedback_at, match_at, True),
            ("on feedback deadline", match_at, feedback_at, feedback_at, True),
            ("inside", match_at, feedback_at, self.NOW, True),
            ("before", match_at, feedback_at, match_at - self.MICRO, False),
            ("after", match_at, feedback_at, feedback_at + self.MICRO, False),
            ("no match notification", None, feedback_at, self.NOW, False),
            ("no feedback deadline", match_at, None, self.NOW, False),
        )

        for label, match, feedback, now, expected in cases:
            with self.subTest(label):
                with patch("backend.mentorship.rounds_service.datetime") as mock_dt:
                    mock_dt.now.return_value = now
                    self.mock_repo.get_latest_promoted_round.return_value = self._round(
                        12,
                        promotion_start_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
                        onboarding_deadline_at=datetime(
                            2026, 6, 1, tzinfo=timezone.utc
                        ),
                        match_notification_at=match,
                        feedback_deadline_at=feedback,
                    )

                    slots = await self._slots()

                self.assertEqual(slots.can_view_match, expected)

    async def test_can_view_match_ignores_another_rounds_window(self):
        """Registration is on a round not announced yet while an older round
        is inside its own announcement window: the match result speaks about
        the registration round, so it cannot be viewed."""
        self.mock_repo.get_open_registration_round.return_value = self._round(
            21,
            "2026 Fall",
            promotion_start_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
            onboarding_deadline_at=datetime(2026, 8, 30, tzinfo=timezone.utc),
            match_notification_at=datetime(2026, 9, 5, tzinfo=timezone.utc),
            feedback_deadline_at=datetime(2027, 3, 1, tzinfo=timezone.utc),
        )
        announced = self._round(
            20,
            "2026 Summer",
            promotion_start_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
            onboarding_deadline_at=datetime(2026, 5, 20, tzinfo=timezone.utc),
            match_notification_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
            feedback_deadline_at=datetime(2026, 12, 1, tzinfo=timezone.utc),
        )
        self.mock_repo.get_latest_promoted_round.return_value = announced
        self.mock_repo.get_all_rounds.return_value = [announced]

        slots = await self._slots()

        self.assertEqual(slots.registration_round_id, 21)
        self.assertEqual(slots.registration_round_name, "2026 Fall")
        self.assertFalse(slots.can_view_match)

    async def test_can_view_match_from_the_fallback_round_once_announced(self):
        self.mock_repo.get_latest_promoted_round.return_value = self._round(
            22,
            "2026 Summer",
            promotion_start_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
            onboarding_deadline_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
            match_notification_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
            feedback_deadline_at=datetime(2026, 12, 1, tzinfo=timezone.utc),
        )

        slots = await self._slots()

        self.assertEqual(slots.registration_round_id, 22)
        self.assertEqual(slots.registration_round_name, "2026 Summer")
        self.assertFalse(slots.is_registration_open)
        self.assertTrue(slots.can_view_match)

    # NOW (08-15) is after the reminder and the derived opening (08-01) but
    # before the meetings deadline and feedback_start_at. The derived close
    # (10-01) is after the feedback deadline.
    REMINDER = datetime(2026, 8, 10, tzinfo=timezone.utc)
    MEETINGS = datetime(2026, 9, 1, tzinfo=timezone.utc)
    FEEDBACK_START = datetime(2026, 9, 5, tzinfo=timezone.utc)
    FEEDBACK_DEADLINE = datetime(2026, 9, 20, tzinfo=timezone.utc)
    DERIVED_CLOSE = datetime(2026, 10, 1, tzinfo=timezone.utc)

    def _in_feedback(self, round_id, **overrides):
        dates = dict(
            promotion_start_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
            onboarding_deadline_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
            match_notification_at=datetime(2026, 4, 15, tzinfo=timezone.utc),
            meeting_log_reminder_at=self.REMINDER,
            meetings_completion_deadline_at=self.MEETINGS,
            feedback_start_at=self.FEEDBACK_START,
            feedback_deadline_at=self.FEEDBACK_DEADLINE,
        )
        dates.update(overrides)
        return self._round(round_id, **dates)

    async def _feedback_enabled_at(self, now, rounds) -> bool:
        self.mock_repo.get_all_rounds.return_value = rounds
        with patch("backend.mentorship.rounds_service.datetime") as mock_dt:
            mock_dt.now.return_value = now
            slots = await self._slots()
        return slots.is_feedback_enabled

    async def test_feedback_enabled_before_the_meetings_deadline(self):
        """The window opens at the reminder, while meetings are still running."""
        self.assertLess(self.NOW, self.MEETINGS)

        self.assertTrue(
            await self._feedback_enabled_at(self.NOW, [self._in_feedback(1)])
        )

    async def test_feedback_enabled_bounds_are_inclusive(self):
        r = self._in_feedback(1)
        cases = (
            (self.REMINDER - self.MICRO, False),
            (self.REMINDER, True),
            (self.FEEDBACK_DEADLINE, True),
            (self.FEEDBACK_DEADLINE + self.MICRO, False),
        )

        for now, expected in cases:
            with self.subTest(now=now):
                self.assertEqual(await self._feedback_enabled_at(now, [r]), expected)

    async def test_feedback_enabled_without_a_feedback_deadline(self):
        """The close falls back to a month past the meetings deadline."""
        r = self._in_feedback(1, feedback_deadline_at=None)

        self.assertTrue(
            await self._feedback_enabled_at(self.FEEDBACK_DEADLINE + self.MICRO, [r])
        )
        self.assertTrue(await self._feedback_enabled_at(self.DERIVED_CLOSE, [r]))
        self.assertFalse(
            await self._feedback_enabled_at(self.DERIVED_CLOSE + self.MICRO, [r])
        )

    async def test_feedback_not_enabled_for_an_unpromoted_round(self):
        r = self._in_feedback(1, promotion_start_at=None)

        self.assertFalse(await self._feedback_enabled_at(self.NOW, [r]))

    async def test_feedback_enabled_by_any_round(self):
        """A closed round listed first does not hide an open one after it."""
        closed = self._in_feedback(
            1,
            meeting_log_reminder_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
            meetings_completion_deadline_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
            feedback_start_at=datetime(2026, 4, 5, tzinfo=timezone.utc),
            feedback_deadline_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
        )
        unpromoted = self._in_feedback(2, promotion_start_at=None)

        self.assertFalse(
            await self._feedback_enabled_at(self.NOW, [closed, unpromoted])
        )
        self.assertTrue(
            await self._feedback_enabled_at(
                self.NOW, [closed, unpromoted, self._in_feedback(3)]
            )
        )

    async def test_feedback_and_registration_are_reported_together(self):
        self.mock_repo.get_open_registration_round.return_value = self._round(
            31,
            promotion_start_at=datetime(2026, 8, 10, tzinfo=timezone.utc),
            onboarding_deadline_at=datetime(2026, 8, 25, tzinfo=timezone.utc),
        )
        self.mock_repo.get_all_rounds.return_value = [self._in_feedback(30)]

        slots = await self._slots()

        self.assertEqual(slots.registration_round_id, 31)
        self.assertTrue(slots.is_registration_open)
        self.assertTrue(slots.is_feedback_enabled)

    def _upcoming(self, round_id):
        return self._round(
            round_id,
            match_notification_at=datetime(2026, 9, 10, tzinfo=timezone.utc),
            meetings_completion_deadline_at=datetime(2027, 1, 1, tzinfo=timezone.utc),
        )

    def _active(self, round_id):
        return self._round(
            round_id,
            match_notification_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
            meetings_completion_deadline_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
        )

    def _completed(self, round_id):
        return self._round(
            round_id,
            match_notification_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            meetings_completion_deadline_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
        )

    async def test_active_round_id_prefers_active_over_upcoming(self):
        """The upcoming round comes first in the list, so taking the first
        round with any status would pick it."""
        self.mock_repo.get_all_rounds.return_value = [
            self._upcoming(41),
            self._active(42),
            self._completed(43),
        ]

        slots = await self._slots()

        self.assertEqual(slots.active_round_id, 42)

    async def test_active_round_id_follows_get_all_rounds_order(self):
        """With two rounds in the same status, the first listed wins, not the
        lowest or highest id."""
        cases = {
            "active": [
                self._completed(50),
                self._active(52),
                self._active(51),
                self._active(53),
            ],
            "upcoming": [
                self._completed(60),
                self._upcoming(62),
                self._upcoming(61),
                self._upcoming(63),
            ],
        }
        expected = {"active": 52, "upcoming": 62}

        for label, rounds in cases.items():
            with self.subTest(label):
                self.mock_repo.get_all_rounds.return_value = rounds

                slots = await self._slots()

                self.assertEqual(slots.active_round_id, expected[label])

    async def test_active_round_id_falls_back_to_upcoming(self):
        self.mock_repo.get_all_rounds.return_value = [
            self._completed(71),
            self._upcoming(72),
        ]

        slots = await self._slots()

        self.assertEqual(slots.active_round_id, 72)

    async def test_active_round_id_none_without_an_active_or_upcoming_round(self):
        self.mock_repo.get_all_rounds.return_value = [
            self._completed(81),
            self._round(82),
        ]

        slots = await self._slots()

        self.assertIsNone(slots.active_round_id)


if __name__ == "__main__":
    unittest.main()
