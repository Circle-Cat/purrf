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
                required_meetings=5,
                onboarding_deadline_at=datetime(2025, 2, 15, tzinfo=timezone.utc),
                meetings_completion_deadline_at=datetime(
                    2025, 6, 30, tzinfo=timezone.utc
                ),
            ),
            MentorshipRoundEntity(
                name="2025-fall",
                mentee_average_score=4.8,
                mentor_average_score=4.6,
                expectations="guiding career development paths",
                required_meetings=5,
                onboarding_deadline_at=datetime(2025, 8, 15, tzinfo=timezone.utc),
                meetings_completion_deadline_at=datetime(
                    2025, 12, 31, tzinfo=timezone.utc
                ),
            ),
        ]

    async def test_get_all_rounds(self):
        """Test retrieve all mentorship round entities, latest meetings
        deadline first."""
        await self.insert_entities(self.rounds)

        rounds = await self.repo.get_all_rounds(self.session)

        expected = [self.rounds[1], self.rounds[0]]
        self.assertEqual(len(rounds), len(expected))

        for round_entity, expected_round in zip(rounds, expected):
            self.assertEqual(round_entity.name, expected_round.name)
            self.assertAlmostEqual(
                round_entity.mentee_average_score, expected_round.mentee_average_score
            )
            self.assertAlmostEqual(
                round_entity.mentor_average_score, expected_round.mentor_average_score
            )
            self.assertEqual(round_entity.expectations, expected_round.expectations)
            self.assertEqual(
                round_entity.onboarding_deadline_at,
                expected_round.onboarding_deadline_at,
            )
            self.assertEqual(
                round_entity.meetings_completion_deadline_at,
                expected_round.meetings_completion_deadline_at,
            )
            self.assertEqual(
                round_entity.required_meetings, expected_round.required_meetings
            )

    async def test_get_all_rounds_orders_by_meetings_deadline_then_created(self):
        """Latest meetings deadline first, rounds without one last, and ties
        broken by the newest created_datetime. The ids follow neither order,
        and the two ties break in opposite id directions, so neither id
        order nor insertion order can pass."""

        def _round(round_id, meetings_deadline, created):
            return MentorshipRoundEntity(
                round_id=round_id,
                name=f"round-{round_id}",
                required_meetings=5,
                onboarding_deadline_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                meetings_completion_deadline_at=meetings_deadline,
                created_datetime=created,
            )

        june = datetime(2026, 6, 30, tzinfo=timezone.utc)
        await self.insert_entities([
            _round(9003, None, datetime(2025, 1, 1, tzinfo=timezone.utc)),
            _round(9001, june, datetime(2025, 5, 1, tzinfo=timezone.utc)),
            _round(9004, None, datetime(2025, 3, 1, tzinfo=timezone.utc)),
            _round(9005, june, datetime(2025, 2, 1, tzinfo=timezone.utc)),
            _round(
                9002,
                datetime(2026, 12, 31, tzinfo=timezone.utc),
                datetime(2025, 4, 1, tzinfo=timezone.utc),
            ),
        ])

        rounds = await self.repo.get_all_rounds(self.session)

        self.assertEqual([r.round_id for r in rounds], [9002, 9001, 9005, 9004, 9003])

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
        self.assertEqual(
            result.onboarding_deadline_at, expected_round.onboarding_deadline_at
        )
        self.assertEqual(
            result.meetings_completion_deadline_at,
            expected_round.meetings_completion_deadline_at,
        )
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
            required_meetings=5,
            promotion_start_at=datetime(2026, 1, 5, tzinfo=timezone.utc),
            onboarding_deadline_at=datetime(2026, 2, 20, tzinfo=timezone.utc),
            match_notification_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
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
            inserted_mentorship_round.onboarding_deadline_at,
            datetime(2026, 2, 20, tzinfo=timezone.utc),
        )
        self.assertEqual(
            inserted_mentorship_round.match_notification_at,
            datetime(2026, 3, 1, tzinfo=timezone.utc),
        )
        self.assertIsNone(inserted_mentorship_round.feedback_deadline_at)
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
            required_meetings=7,
            onboarding_deadline_at=datetime(2025, 3, 1, tzinfo=timezone.utc),
        )

        updated_mentorship_round = await self.repo.upsert_round(
            self.session, updated_entity
        )

        self.assertEqual(updated_mentorship_round.name, "2025-spring-updated")
        self.assertEqual(updated_mentorship_round.mentee_average_score, 4.4)
        self.assertEqual(updated_mentorship_round.required_meetings, 7)
        self.assertEqual(
            updated_mentorship_round.onboarding_deadline_at,
            datetime(2025, 3, 1, tzinfo=timezone.utc),
        )

    async def _seed_round(
        self, match_notification_at=None, meetings_completion_deadline_at=None
    ):
        """Insert a MentorshipRoundEntity with the given meeting window."""
        round_entity = MentorshipRoundEntity(
            name="seeded-round",
            required_meetings=5,
            onboarding_deadline_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
            match_notification_at=match_notification_at,
            meetings_completion_deadline_at=meetings_completion_deadline_at,
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
            required_meetings=5,
            onboarding_deadline_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
            match_notification_at=now - timedelta(days=7),
            meetings_completion_deadline_at=now + timedelta(days=7),
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
            required_meetings=5,
            onboarding_deadline_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
            match_notification_at=now - timedelta(seconds=1),
            meetings_completion_deadline_at=now + timedelta(days=7),
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
            required_meetings=5,
            onboarding_deadline_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
            match_notification_at=deadline - timedelta(days=7),
            meetings_completion_deadline_at=deadline,
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
            required_meetings=5,
            onboarding_deadline_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
            match_notification_at=now + timedelta(days=1),
            meetings_completion_deadline_at=now + timedelta(days=7),
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
            required_meetings=5,
            onboarding_deadline_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
            match_notification_at=now - timedelta(days=7),
            meetings_completion_deadline_at=now - timedelta(days=1),
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

    async def test_running_rounds_without_a_meeting_window(self):
        """Test returns an empty list (not an error) for a round whose
        meeting window columns are unset."""
        round_entity = MentorshipRoundEntity(
            name="no-dates-round",
            required_meetings=5,
            onboarding_deadline_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
        )
        await self.insert_entities([round_entity])

        with patch(
            "backend.repository.mentorship_round_repository.datetime"
        ) as mock_datetime:
            mock_datetime.now.return_value = self._FIXED_NOW
            rows = await self.repo.get_running_rounds(self.session, timedelta(0))

        self.assertEqual(rows, [])

    async def test_running_rounds_with_only_one_window_bound(self):
        """Test a round is not running unless both bounds are set, whichever
        one is missing."""
        await self._seed_round(
            match_notification_at=self._FIXED_NOW - timedelta(days=7)
        )
        await self._seed_round(
            meetings_completion_deadline_at=self._FIXED_NOW + timedelta(days=7)
        )

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

    # --- get_running_rounds ---

    async def test_running_rounds_returns_the_window_bounds(self):
        round_ = await self._seed_round(
            match_notification_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
            meetings_completion_deadline_at=datetime(2026, 4, 30, tzinfo=timezone.utc),
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
            match_notification_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
            meetings_completion_deadline_at=datetime(2026, 4, 30, tzinfo=timezone.utc),
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
            match_notification_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
            meetings_completion_deadline_at=datetime(2026, 4, 30, tzinfo=timezone.utc),
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

    async def test_running_rounds_orders_overlapping_rounds_deterministically(self):
        """Two rounds covering `now` must come back in ascending round_id, so
        the caller processes and reports them in a fixed order.

        The first round is UPDATEd after both are seeded, and that touch is
        what gives this test teeth. Under MVCC an UPDATE writes a NEW row
        version at the end of the heap and marks the old one dead, so an
        unordered SELECT hands the pair back with the updated row LAST -- i.e.
        out of insertion order, and out of round_id order. Seed-only, both rows
        sit in insertion order and the heap order coincides with the expected
        ascending order, so dropping `.order_by(...)` entirely -- exactly the
        pre-branch bug this test is named for -- used to pass here unnoticed;
        only a reversal to `.desc()` was caught.
        """
        first = await self._seed_round(
            match_notification_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
            meetings_completion_deadline_at=datetime(2026, 4, 30, tzinfo=timezone.utc),
        )
        second = await self._seed_round(
            match_notification_at=datetime(2026, 4, 10, tzinfo=timezone.utc),
            meetings_completion_deadline_at=datetime(2026, 5, 10, tzinfo=timezone.utc),
        )
        repo = MentorshipRoundRepository()
        # Rewrite the LOWER-id row so the heap now yields it second. Any UPDATE
        # to that row would do; this one is the cheapest column to disturb and
        # is not read by get_running_rounds.
        await repo.update_mentee_average_score(
            self.session, round_id=first.round_id, value=4.2
        )
        self.assertLess(first.round_id, second.round_id)

        with patch(
            "backend.repository.mentorship_round_repository.datetime"
        ) as mock_datetime:
            mock_datetime.now.return_value = datetime(2026, 4, 15, tzinfo=timezone.utc)
            rows = await repo.get_running_rounds(self.session, timedelta(hours=8))

        self.assertEqual(
            [r.round_id for r in rows], sorted([first.round_id, second.round_id])
        )


class TestGetOpenRegistrationRound(BaseRepositoryTestLib):
    """The round open for registration at a given instant."""

    # Before self.now, so these fixtures vary only the deadlines.
    PROMOTION_STARTED = datetime(2026, 8, 1, 7, 0, tzinfo=timezone.utc)

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.repo = MentorshipRoundRepository()
        self.now = datetime(2026, 8, 15, tzinfo=timezone.utc)

    def _round(
        self,
        name: str,
        *,
        onboarding_deadline_at: datetime,
        promotion_start_at: datetime | None = PROMOTION_STARTED,
        mentor_application_deadline_at: datetime | None = None,
    ) -> MentorshipRoundEntity:
        return MentorshipRoundEntity(
            name=name,
            required_meetings=5,
            promotion_start_at=promotion_start_at,
            mentor_application_deadline_at=mentor_application_deadline_at,
            onboarding_deadline_at=onboarding_deadline_at,
        )

    async def _select(self):
        return await self.repo.get_open_registration_round(self.session, self.now)

    async def test_returns_the_round_closing_soonest(self):
        """Two windows open at once: the one whose onboarding deadline is
        about to pass is the one to register for. Its mentor application
        deadline is the later one, so ordering by that would pick the other."""
        later = self._round(
            "2027 Spring",
            mentor_application_deadline_at=datetime(2026, 8, 20, tzinfo=timezone.utc),
            onboarding_deadline_at=datetime(2026, 12, 31, 23, 59, tzinfo=timezone.utc),
        )
        sooner = self._round(
            "2026 Fall",
            mentor_application_deadline_at=datetime(2026, 9, 25, tzinfo=timezone.utc),
            onboarding_deadline_at=datetime(2026, 9, 30, 23, 59, tzinfo=timezone.utc),
        )
        await self.insert_entities([later, sooner])

        selected = await self._select()

        self.assertIsNotNone(selected)
        self.assertEqual(selected.name, "2026 Fall")

    async def test_closing_soonest_wins_over_latest_promoted(self):
        """While windows overlap, the round closing soonest wins even though
        another open round started promoting more recently, so the
        latest-promoted rule would pick the other one."""
        await self.insert_entities([
            self._round(
                "2027 Spring",
                promotion_start_at=datetime(2026, 8, 10, tzinfo=timezone.utc),
                onboarding_deadline_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
            ),
            self._round(
                "2026 Fall",
                promotion_start_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
                onboarding_deadline_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
            ),
        ])

        selected = await self._select()

        self.assertIsNotNone(selected)
        self.assertEqual(selected.name, "2026 Fall")

    async def test_stays_open_after_the_mentor_application_deadline(self):
        """Registration closes at the onboarding deadline, so a round whose
        mentor application deadline has already passed is still open."""
        await self.insert_entities([
            self._round(
                "2026 Fall",
                mentor_application_deadline_at=datetime(
                    2026, 8, 10, tzinfo=timezone.utc
                ),
                onboarding_deadline_at=datetime(2026, 8, 31, tzinfo=timezone.utc),
            )
        ])

        selected = await self._select()

        self.assertIsNotNone(selected)
        self.assertEqual(selected.name, "2026 Fall")

    async def test_ignores_rounds_whose_onboarding_deadline_has_passed(self):
        """Closed once onboarding is due, even while the mentor application
        deadline is still ahead."""
        await self.insert_entities([
            self._round(
                "2026 Spring",
                promotion_start_at=datetime(2025, 12, 18, 8, 0, tzinfo=timezone.utc),
                mentor_application_deadline_at=datetime(
                    2026, 9, 30, tzinfo=timezone.utc
                ),
                onboarding_deadline_at=datetime(2026, 8, 10, tzinfo=timezone.utc),
            )
        ])

        self.assertIsNone(await self._select())

    async def test_closed_at_the_onboarding_deadline_itself(self):
        """The deadline instant is already closed."""
        await self.insert_entities([
            self._round("2026 Fall", onboarding_deadline_at=self.now)
        ])

        self.assertIsNone(await self._select())

    async def test_open_one_microsecond_before_the_onboarding_deadline(self):
        await self.insert_entities([
            self._round(
                "2026 Fall",
                onboarding_deadline_at=self.now + timedelta(microseconds=1),
            )
        ])

        selected = await self._select()

        self.assertIsNotNone(selected)
        self.assertEqual(selected.name, "2026 Fall")

    async def test_open_from_the_promotion_start_itself(self):
        await self.insert_entities([
            self._round(
                "2026 Fall",
                promotion_start_at=self.now,
                onboarding_deadline_at=datetime(2026, 9, 30, tzinfo=timezone.utc),
            )
        ])

        selected = await self._select()

        self.assertIsNotNone(selected)
        self.assertEqual(selected.name, "2026 Fall")

    async def test_ignores_rounds_whose_promotion_has_not_started(self):
        """The deadline alone does not open registration: a round in the gap
        between admission and promotion has nothing to register for yet."""
        await self.insert_entities([
            self._round(
                "2026 Fall",
                promotion_start_at=datetime(2026, 8, 18, 7, 0, tzinfo=timezone.utc),
                onboarding_deadline_at=datetime(2026, 9, 30, tzinfo=timezone.utc),
            )
        ])

        self.assertIsNone(await self._select())

    async def test_prefers_the_soonest_deadline_among_promoted_rounds(self):
        """Ordering is by deadline, but only rounds already promoting are
        candidates -- a sooner deadline that has not started promoting yet
        must not shadow the round that can actually be registered for."""
        await self.insert_entities([
            self._round(
                "2026 Fall",
                promotion_start_at=datetime(2026, 8, 18, 7, 0, tzinfo=timezone.utc),
                onboarding_deadline_at=datetime(2026, 8, 25, tzinfo=timezone.utc),
            ),
            self._round(
                "2026 Summer",
                onboarding_deadline_at=datetime(2026, 9, 30, tzinfo=timezone.utc),
            ),
        ])

        selected = await self._select()

        self.assertIsNotNone(selected)
        self.assertEqual(selected.name, "2026 Summer")

    async def test_ignores_rounds_without_a_promotion_start(self):
        await self.insert_entities([
            self._round(
                "2026 Fall",
                promotion_start_at=None,
                onboarding_deadline_at=datetime(2026, 9, 30, tzinfo=timezone.utc),
            )
        ])

        self.assertIsNone(await self._select())

    async def test_open_round_is_independent_of_a_round_in_feedback(self):
        """A round in its feedback phase and a round open for registration
        coexist: each query reports its own round."""
        await self.insert_entities([
            MentorshipRoundEntity(
                name="2026 Spring",
                required_meetings=5,
                promotion_start_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                onboarding_deadline_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
                meetings_completion_deadline_at=datetime(
                    2026, 8, 1, tzinfo=timezone.utc
                ),
                feedback_deadline_at=datetime(2026, 8, 30, tzinfo=timezone.utc),
            ),
            self._round(
                "2026 Fall",
                onboarding_deadline_at=datetime(2026, 8, 25, tzinfo=timezone.utc),
            ),
        ])

        selected = await self._select()

        self.assertIsNotNone(selected)
        self.assertEqual(selected.name, "2026 Fall")
        self.assertTrue(await self.repo.has_round_in_feedback(self.session, self.now))

    async def test_returns_none_when_no_round_qualifies(self):
        self.assertIsNone(await self._select())


class TestGetLatestPromotedRound(BaseRepositoryTestLib):
    """The most recently promoted round, kept viewable once registration
    has closed."""

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.repo = MentorshipRoundRepository()
        self.now = datetime(2026, 8, 15, tzinfo=timezone.utc)

    def _round(
        self,
        name: str,
        promotion_start_at: datetime | None,
        onboarding_deadline_at: datetime,
    ) -> MentorshipRoundEntity:
        return MentorshipRoundEntity(
            name=name,
            required_meetings=5,
            promotion_start_at=promotion_start_at,
            onboarding_deadline_at=onboarding_deadline_at,
        )

    async def _select(self):
        return await self.repo.get_latest_promoted_round(self.session, self.now)

    async def test_picks_the_latest_promotion_start_among_started_rounds(self):
        """The expected round is neither first nor last inserted, and its
        onboarding deadline is neither the earliest nor the latest, so id
        order or a deadline order would pick another round. The rounds not
        yet promoted, or never, would win if they were not excluded."""
        await self.insert_entities([
            self._round(
                "2026 Spring",
                datetime(2026, 1, 1, tzinfo=timezone.utc),
                datetime(2026, 12, 1, tzinfo=timezone.utc),
            ),
            self._round(
                "2026 Fall",
                datetime(2026, 7, 1, tzinfo=timezone.utc),
                datetime(2026, 8, 1, tzinfo=timezone.utc),
            ),
            self._round(
                "2027 Spring",
                datetime(2026, 8, 20, tzinfo=timezone.utc),
                datetime(2026, 9, 30, tzinfo=timezone.utc),
            ),
            self._round(
                "Unscheduled",
                None,
                datetime(2026, 7, 15, tzinfo=timezone.utc),
            ),
            self._round(
                "2026 Summer",
                datetime(2026, 3, 1, tzinfo=timezone.utc),
                datetime(2026, 3, 20, tzinfo=timezone.utc),
            ),
        ])

        selected = await self._select()

        self.assertIsNotNone(selected)
        self.assertEqual(selected.name, "2026 Fall")

    async def test_returns_a_round_whose_registration_has_closed(self):
        await self.insert_entities([
            self._round(
                "2026 Fall",
                datetime(2026, 7, 1, tzinfo=timezone.utc),
                datetime(2026, 8, 1, tzinfo=timezone.utc),
            )
        ])

        selected = await self._select()

        self.assertIsNotNone(selected)
        self.assertEqual(selected.name, "2026 Fall")

    async def test_includes_a_round_promoted_at_now_itself(self):
        await self.insert_entities([
            self._round(
                "2026 Fall",
                self.now,
                datetime(2026, 9, 30, tzinfo=timezone.utc),
            )
        ])

        selected = await self._select()

        self.assertIsNotNone(selected)
        self.assertEqual(selected.name, "2026 Fall")

    async def test_returns_none_when_no_round_has_started_promotion(self):
        await self.insert_entities([
            self._round(
                "2027 Spring",
                self.now + timedelta(microseconds=1),
                datetime(2026, 9, 30, tzinfo=timezone.utc),
            ),
            self._round(
                "Unscheduled",
                None,
                datetime(2026, 7, 15, tzinfo=timezone.utc),
            ),
        ])

        self.assertIsNone(await self._select())

    async def test_returns_none_when_no_rounds_exist(self):
        self.assertIsNone(await self._select())


class TestHasRoundInFeedback(BaseRepositoryTestLib):
    """Whether any promoted round sits between its meetings deadline and
    its feedback deadline."""

    MEETINGS_DEADLINE = datetime(2026, 8, 1, 6, 59, 59, tzinfo=timezone.utc)
    FEEDBACK_DEADLINE = datetime(2026, 8, 20, 6, 59, 59, tzinfo=timezone.utc)

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.repo = MentorshipRoundRepository()

    async def _seed(
        self,
        *,
        promotion_start_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
        meetings_completion_deadline_at=MEETINGS_DEADLINE,
        feedback_deadline_at=FEEDBACK_DEADLINE,
    ):
        await self.insert_entities([
            MentorshipRoundEntity(
                name="2026 Spring",
                required_meetings=5,
                promotion_start_at=promotion_start_at,
                onboarding_deadline_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
                meetings_completion_deadline_at=meetings_completion_deadline_at,
                feedback_deadline_at=feedback_deadline_at,
            )
        ])

    async def test_bounds_are_inclusive_on_both_ends(self):
        await self._seed()
        micro = timedelta(microseconds=1)
        cases = (
            (self.MEETINGS_DEADLINE - micro, False),
            (self.MEETINGS_DEADLINE, True),
            (datetime(2026, 8, 10, tzinfo=timezone.utc), True),
            (self.FEEDBACK_DEADLINE, True),
            (self.FEEDBACK_DEADLINE + micro, False),
        )

        for now, expected in cases:
            with self.subTest(now=now):
                self.assertEqual(
                    await self.repo.has_round_in_feedback(self.session, now), expected
                )

    async def test_false_without_a_feedback_deadline(self):
        await self._seed(feedback_deadline_at=None)

        self.assertFalse(
            await self.repo.has_round_in_feedback(
                self.session, datetime(2026, 8, 10, tzinfo=timezone.utc)
            )
        )

    async def test_false_without_a_promotion_start(self):
        await self._seed(promotion_start_at=None)

        self.assertFalse(
            await self.repo.has_round_in_feedback(
                self.session, datetime(2026, 8, 10, tzinfo=timezone.utc)
            )
        )

    async def test_false_without_a_meetings_deadline(self):
        await self._seed(meetings_completion_deadline_at=None)

        self.assertFalse(
            await self.repo.has_round_in_feedback(
                self.session, datetime(2026, 8, 10, tzinfo=timezone.utc)
            )
        )

    async def test_false_when_no_rounds_exist(self):
        self.assertFalse(
            await self.repo.has_round_in_feedback(
                self.session, datetime(2026, 8, 10, tzinfo=timezone.utc)
            )
        )


if __name__ == "__main__":
    unittest.main()
