import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch
from backend.entity.mentorship_round_entity import MentorshipRoundEntity
from backend.repository.mentorship_round_repository import MentorshipRoundRepository
from tests.backend_test.repository_test.base_repository_test_lib import (
    BaseRepositoryTestLib,
)


class TestMentorShipRoundRepository(BaseRepositoryTestLib):
    async def asyncSetUp(self):
        await super().asyncSetUp()

        self.repo = MentorshipRoundRepository()

        self.rounds = [
            MentorshipRoundEntity(
                name="2025-spring",
                mentee_average_score=4.3,
                mentor_average_score=4.5,
                expectations="improving mentee's ability",
                description={"goal": "basic skills"},
                required_meetings=5,
            ),
            MentorshipRoundEntity(
                name="2025-fall",
                mentee_average_score=4.8,
                mentor_average_score=4.6,
                expectations="guiding career development paths",
                description={"goal": "career planning"},
                required_meetings=5,
            ),
        ]

    async def test_get_all_rounds(self):
        """Test retrieve all mentorship round entities"""
        await self.insert_entities(self.rounds)

        rounds = await self.repo.get_all_rounds(self.session)

        self.assertEqual(len(rounds), len(self.rounds))

        for i, round_entity in enumerate(rounds):
            self.assertEqual(round_entity.name, self.rounds[i].name)
            self.assertAlmostEqual(
                round_entity.mentee_average_score, self.rounds[i].mentee_average_score
            )
            self.assertAlmostEqual(
                round_entity.mentor_average_score, self.rounds[i].mentor_average_score
            )
            self.assertEqual(round_entity.expectations, self.rounds[i].expectations)
            self.assertEqual(round_entity.description, self.rounds[i].description)
            self.assertEqual(
                round_entity.required_meetings, self.rounds[i].required_meetings
            )

    async def test_get_all_rounds_empty(self):
        """Test retrieve an empty list when no mentorship rounds exist."""
        rounds = await self.repo.get_all_rounds(self.session)

        self.assertIsInstance(rounds, list)
        self.assertEqual(rounds, [])

    async def test_get_by_round_id_success(self):
        """Test successful retrieval of mentorship round by round_id"""
        await self.insert_entities(self.rounds)

        round_id = self.rounds[0].round_id
        expected_round = self.rounds[0]

        result = await self.repo.get_by_round_id(self.session, round_id)

        self.assertIsNotNone(result)
        self.assertEqual(result.round_id, expected_round.round_id)
        self.assertEqual(result.name, expected_round.name)
        self.assertAlmostEqual(
            result.mentee_average_score, expected_round.mentee_average_score
        )
        self.assertAlmostEqual(
            result.mentor_average_score, expected_round.mentor_average_score
        )
        self.assertEqual(result.expectations, expected_round.expectations)
        self.assertEqual(result.description, expected_round.description)
        self.assertEqual(result.required_meetings, expected_round.required_meetings)

    async def test_get_by_round_id_not_found(self):
        """Test when mentorship round is not found then None."""
        round_id = 9999

        result = await self.repo.get_by_round_id(self.session, round_id)
        self.assertIsNone(result)

    async def test_get_by_round_id_invalid(self):
        """Test when mentorship round is invalid then None."""
        result = await self.repo.get_by_round_id(self.session, None)

        self.assertIsNone(result)

    async def test_upsert_round_insert_mentorship_round_entity(self):
        """Test insert a new MentorshipRoundEntity"""
        new_mentorship_round = MentorshipRoundEntity(
            name="2026-spring",
            mentee_average_score=4.9,
            mentor_average_score=4.2,
            expectations="explaining complicated concepts",
            description={"goal": "understanding knowledge"},
            required_meetings=5,
        )

        inserted_mentorship_round = await self.repo.upsert_round(
            self.session, new_mentorship_round
        )

        self.assertIsNotNone(inserted_mentorship_round.round_id)
        self.assertEqual(inserted_mentorship_round.name, new_mentorship_round.name)
        self.assertEqual(
            inserted_mentorship_round.mentee_average_score,
            new_mentorship_round.mentee_average_score,
        )
        self.assertEqual(
            inserted_mentorship_round.mentor_average_score,
            new_mentorship_round.mentor_average_score,
        )
        self.assertEqual(
            inserted_mentorship_round.expectations, new_mentorship_round.expectations
        )
        self.assertEqual(
            inserted_mentorship_round.description, new_mentorship_round.description
        )
        self.assertEqual(
            inserted_mentorship_round.required_meetings,
            new_mentorship_round.required_meetings,
        )

    async def test_upsert_users_update_mentorship_round_entity(self):
        """Test update a existed MentorshipRoundEntity"""
        existing_mentorship_round = self.rounds[0]
        await self.insert_entities([existing_mentorship_round])

        updated_entity = MentorshipRoundEntity(
            round_id=existing_mentorship_round.round_id,
            name="2025-spring-updated",
            mentee_average_score=4.4,
            mentor_average_score=4.7,
            expectations="improving mentee's ability - updated",
            description={"goal": "improving skills"},
            required_meetings=7,
        )

        updated_mentorship_round = await self.repo.upsert_round(
            self.session, updated_entity
        )

        self.assertEqual(updated_mentorship_round.name, "2025-spring-updated")
        self.assertEqual(updated_mentorship_round.mentee_average_score, 4.4)
        self.assertEqual(updated_mentorship_round.required_meetings, 7)

    async def _seed_round(
        self, match_notification_at=None, meetings_completion_deadline_at=None
    ):
        """Insert a MentorshipRoundEntity with the given timeline strings.

        Reused across the get_running_rounds tests: some pass full ISO
        timestamps, others a bare YYYY-MM-DD form.
        """
        round_entity = MentorshipRoundEntity(
            name="seeded-round",
            description={
                "match_notification_at": match_notification_at,
                "meetings_completion_deadline_at": meetings_completion_deadline_at,
            },
            required_meetings=5,
        )
        await self.insert_entities([round_entity])
        return round_entity

    # A fixed reference instant, deliberately outside the shared test
    # database's known residue window (rounds with a wide-open window
    # spanning 2026-07-24 through 2026-12-01). The old tests below used the
    # real wall-clock `datetime.now(timezone.utc)`, which -- on any day that
    # falls inside that residue window, i.e. right now -- makes a leftover
    # residue round match right along with the one each test seeds. Mocking
    # `datetime.now` to this fixed instant, the same way the other
    # get_running_rounds tests already do, keeps these tests deterministic
    # and independent of both the wall clock and the residue.
    _FIXED_NOW = datetime(2026, 4, 15, tzinfo=timezone.utc)

    async def test_running_rounds_within_window(self):
        """Test returns the round when now falls within the meeting window."""
        now = self._FIXED_NOW
        round_entity = MentorshipRoundEntity(
            name="active-round",
            description={
                "match_notification_at": (now - timedelta(days=7)).isoformat(),
                "meetings_completion_deadline_at": (
                    now + timedelta(days=7)
                ).isoformat(),
            },
            required_meetings=5,
        )
        await self.insert_entities([round_entity])

        with patch(
            "backend.repository.mentorship_round_repository.datetime"
        ) as mock_datetime:
            mock_datetime.now.return_value = now
            rows = await self.repo.get_running_rounds(self.session, timedelta(0))

        self.assertEqual([r.round_id for r in rows], [round_entity.round_id])

    async def test_running_rounds_on_start_boundary(self):
        """Test returns the round when match_notification_at is just before now (inclusive)."""
        now = self._FIXED_NOW
        round_entity = MentorshipRoundEntity(
            name="start-boundary-round",
            description={
                "match_notification_at": (now - timedelta(seconds=1)).isoformat(),
                "meetings_completion_deadline_at": (
                    now + timedelta(days=7)
                ).isoformat(),
            },
            required_meetings=5,
        )
        await self.insert_entities([round_entity])

        with patch(
            "backend.repository.mentorship_round_repository.datetime"
        ) as mock_datetime:
            mock_datetime.now.return_value = now
            rows = await self.repo.get_running_rounds(self.session, timedelta(0))

        self.assertEqual([r.round_id for r in rows], [round_entity.round_id])

    async def test_running_rounds_on_end_boundary(self):
        """Test returns the round when now is exactly meetings_completion_deadline_at
        (inclusive), with zero grace -- so the inclusive boundary is on the
        deadline itself, not on an approximation of it."""
        deadline = self._FIXED_NOW
        round_entity = MentorshipRoundEntity(
            name="end-boundary-round",
            description={
                "match_notification_at": (deadline - timedelta(days=7)).isoformat(),
                "meetings_completion_deadline_at": deadline.isoformat(),
            },
            required_meetings=5,
        )
        await self.insert_entities([round_entity])

        with patch(
            "backend.repository.mentorship_round_repository.datetime"
        ) as mock_datetime:
            mock_datetime.now.return_value = deadline
            rows = await self.repo.get_running_rounds(self.session, timedelta(0))

        self.assertEqual([r.round_id for r in rows], [round_entity.round_id])

    async def test_running_rounds_before_window(self):
        """Test returns nothing when now is before match_notification_at."""
        now = self._FIXED_NOW
        round_entity = MentorshipRoundEntity(
            name="future-round",
            description={
                "match_notification_at": (now + timedelta(days=1)).isoformat(),
                "meetings_completion_deadline_at": (
                    now + timedelta(days=7)
                ).isoformat(),
            },
            required_meetings=5,
        )
        await self.insert_entities([round_entity])

        with patch(
            "backend.repository.mentorship_round_repository.datetime"
        ) as mock_datetime:
            mock_datetime.now.return_value = now
            rows = await self.repo.get_running_rounds(self.session, timedelta(0))

        self.assertEqual(rows, [])

    async def test_running_rounds_after_window_with_no_grace_returns_nothing(self):
        """Test returns nothing when now is well past meetings_completion_deadline_at
        and there is no grace to extend the selection.

        The old ``after_window`` case's other half -- past the deadline but
        still inside the grace period -- is covered by
        ``test_running_rounds_grace_extends_only_the_selection``, which
        asserts the round is still returned in that situation.
        """
        now = self._FIXED_NOW
        round_entity = MentorshipRoundEntity(
            name="past-round",
            description={
                "match_notification_at": (now - timedelta(days=7)).isoformat(),
                "meetings_completion_deadline_at": (
                    now - timedelta(days=1)
                ).isoformat(),
            },
            required_meetings=5,
        )
        await self.insert_entities([round_entity])

        with patch(
            "backend.repository.mentorship_round_repository.datetime"
        ) as mock_datetime:
            mock_datetime.now.return_value = now
            rows = await self.repo.get_running_rounds(self.session, timedelta(0))

        self.assertEqual(rows, [])

    async def test_running_rounds_no_rounds(self):
        """Test returns an empty list when no rounds exist."""
        with patch(
            "backend.repository.mentorship_round_repository.datetime"
        ) as mock_datetime:
            mock_datetime.now.return_value = self._FIXED_NOW
            rows = await self.repo.get_running_rounds(self.session, timedelta(0))

        self.assertEqual(rows, [])

    async def test_running_rounds_missing_date_fields(self):
        """Test returns an empty list (not an error) when description lacks
        the required date keys."""
        round_entity = MentorshipRoundEntity(
            name="no-dates-round",
            description={"goal": "no dates here"},
            required_meetings=5,
        )
        await self.insert_entities([round_entity])

        with patch(
            "backend.repository.mentorship_round_repository.datetime"
        ) as mock_datetime:
            mock_datetime.now.return_value = self._FIXED_NOW
            rows = await self.repo.get_running_rounds(self.session, timedelta(0))

        self.assertEqual(rows, [])

    async def test_running_rounds_null_date_values(self):
        """Test returns an empty list (not an error) when date keys exist but
        their values are JSON null."""
        round_entity = MentorshipRoundEntity(
            name="null-dates-round",
            description={
                "match_notification_at": None,
                "meetings_completion_deadline_at": None,
            },
            required_meetings=5,
        )
        await self.insert_entities([round_entity])

        with patch(
            "backend.repository.mentorship_round_repository.datetime"
        ) as mock_datetime:
            mock_datetime.now.return_value = self._FIXED_NOW
            rows = await self.repo.get_running_rounds(self.session, timedelta(0))

        self.assertEqual(rows, [])

    async def test_update_mentee_average_score(self):
        """Updates mentee_average_score while leaving mentor_average_score unchanged."""
        await self.insert_entities([self.rounds[0]])

        await self.repo.update_mentee_average_score(
            self.session, round_id=self.rounds[0].round_id, value=3.7
        )

        result = await self.repo.get_by_round_id(self.session, self.rounds[0].round_id)
        self.assertAlmostEqual(result.mentee_average_score, 3.7)
        self.assertAlmostEqual(
            result.mentor_average_score, self.rounds[0].mentor_average_score
        )

    async def test_update_mentor_average_score(self):
        """Updates mentor_average_score while leaving mentee_average_score unchanged."""
        await self.insert_entities([self.rounds[0]])

        await self.repo.update_mentor_average_score(
            self.session, round_id=self.rounds[0].round_id, value=2.5
        )

        result = await self.repo.get_by_round_id(self.session, self.rounds[0].round_id)
        self.assertAlmostEqual(result.mentor_average_score, 2.5)
        self.assertAlmostEqual(
            result.mentee_average_score, self.rounds[0].mentee_average_score
        )

    async def test_update_mentee_average_score_to_none(self):
        """Clears mentee_average_score by setting it to None."""
        await self.insert_entities([self.rounds[0]])

        await self.repo.update_mentee_average_score(
            self.session, round_id=self.rounds[0].round_id, value=None
        )

        result = await self.repo.get_by_round_id(self.session, self.rounds[0].round_id)
        self.assertIsNone(result.mentee_average_score)

    async def test_running_rounds_null_description(self):
        """Test returns an empty list (not an error) when description itself
        is null."""
        round_entity = MentorshipRoundEntity(
            name="null-description-round",
            description=None,
            required_meetings=5,
        )
        await self.insert_entities([round_entity])

        with patch(
            "backend.repository.mentorship_round_repository.datetime"
        ) as mock_datetime:
            mock_datetime.now.return_value = self._FIXED_NOW
            rows = await self.repo.get_running_rounds(self.session, timedelta(0))

        self.assertEqual(rows, [])

    # --- get_running_rounds ---

    async def test_running_rounds_returns_the_window_bounds(self):
        round_ = await self._seed_round(
            match_notification_at="2026-04-01T00:00:00+00:00",
            meetings_completion_deadline_at="2026-04-30T00:00:00+00:00",
        )
        repo = MentorshipRoundRepository()

        with patch(
            "backend.repository.mentorship_round_repository.datetime"
        ) as mock_datetime:
            mock_datetime.now.return_value = datetime(2026, 4, 15, tzinfo=timezone.utc)
            rows = await repo.get_running_rounds(self.session, timedelta(hours=8))

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].round_id, round_.round_id)
        self.assertEqual(
            rows[0].window_start, datetime(2026, 4, 1, tzinfo=timezone.utc)
        )
        self.assertEqual(rows[0].window_end, datetime(2026, 4, 30, tzinfo=timezone.utc))

    async def test_running_rounds_grace_extends_only_the_selection(self):
        """Inside the grace the round is still returned, and window_end is
        still the un-widened deadline -- the grace must not leak into the
        bounds meetings get filtered against."""
        await self._seed_round(
            match_notification_at="2026-04-01T00:00:00+00:00",
            meetings_completion_deadline_at="2026-04-30T00:00:00+00:00",
        )
        repo = MentorshipRoundRepository()

        with patch(
            "backend.repository.mentorship_round_repository.datetime"
        ) as mock_datetime:
            mock_datetime.now.return_value = datetime(
                2026,
                4,
                30,
                6,
                0,
                tzinfo=timezone.utc,  # deadline + 6h
            )
            rows = await repo.get_running_rounds(self.session, timedelta(hours=8))

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].window_end, datetime(2026, 4, 30, tzinfo=timezone.utc))

    async def test_running_rounds_past_the_grace_returns_nothing(self):
        await self._seed_round(
            match_notification_at="2026-04-01T00:00:00+00:00",
            meetings_completion_deadline_at="2026-04-30T00:00:00+00:00",
        )
        repo = MentorshipRoundRepository()

        with patch(
            "backend.repository.mentorship_round_repository.datetime"
        ) as mock_datetime:
            mock_datetime.now.return_value = datetime(
                2026,
                4,
                30,
                10,
                0,
                tzinfo=timezone.utc,  # deadline + 10h > 8h grace
            )
            rows = await repo.get_running_rounds(self.session, timedelta(hours=8))

        self.assertEqual(rows, [])

    async def test_running_rounds_tolerates_a_bare_date_timeline(self):
        """backfill writes YYYY-MM-DD while rounds_service writes ISO with an
        offset. The cast happens in SQL precisely so both work; isoparse would
        return a naive datetime for the bare form and raise on comparison."""
        round_ = await self._seed_round(
            match_notification_at="2026-04-01",
            meetings_completion_deadline_at="2026-04-30",
        )
        repo = MentorshipRoundRepository()

        with patch(
            "backend.repository.mentorship_round_repository.datetime"
        ) as mock_datetime:
            mock_datetime.now.return_value = datetime(2026, 4, 15, tzinfo=timezone.utc)
            rows = await repo.get_running_rounds(self.session, timedelta(hours=8))

        self.assertEqual([r.round_id for r in rows], [round_.round_id])
        self.assertIsNotNone(rows[0].window_start.tzinfo)

    async def test_running_rounds_orders_overlapping_rounds_deterministically(self):
        """Two rounds covering `now` must come back in a fixed order, so the
        caller always picks the same one and can report the other."""
        first = await self._seed_round(
            match_notification_at="2026-04-01T00:00:00+00:00",
            meetings_completion_deadline_at="2026-04-30T00:00:00+00:00",
        )
        second = await self._seed_round(
            match_notification_at="2026-04-10T00:00:00+00:00",
            meetings_completion_deadline_at="2026-05-10T00:00:00+00:00",
        )
        repo = MentorshipRoundRepository()

        with patch(
            "backend.repository.mentorship_round_repository.datetime"
        ) as mock_datetime:
            mock_datetime.now.return_value = datetime(2026, 4, 15, tzinfo=timezone.utc)
            rows = await repo.get_running_rounds(self.session, timedelta(hours=8))

        self.assertEqual(
            [r.round_id for r in rows], sorted([first.round_id, second.round_id])
        )


if __name__ == "__main__":
    unittest.main()
