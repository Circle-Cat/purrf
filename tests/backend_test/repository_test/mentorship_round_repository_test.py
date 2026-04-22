import unittest
from datetime import datetime, timezone, timedelta
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

    async def test_get_running_round_id_within_window(self):
        """Test returns round_id when now falls within the meeting window."""
        now = datetime.now(timezone.utc)
        round_entity = MentorshipRoundEntity(
            name="active-round",
            description={
                "match_notification_at": (now - timedelta(days=7)).isoformat(),
                "meetings_completion_deadline_at": (now + timedelta(days=7)).isoformat(),
            },
            required_meetings=5,
        )
        await self.insert_entities([round_entity])

        result = await self.repo.get_running_round_id(self.session)

        self.assertEqual(result, round_entity.round_id)

    async def test_get_running_round_id_on_start_boundary(self):
        """Test returns round_id when match_notification_at is just before now (inclusive)."""
        now = datetime.now(timezone.utc)
        round_entity = MentorshipRoundEntity(
            name="start-boundary-round",
            description={
                "match_notification_at": (now - timedelta(seconds=1)).isoformat(),
                "meetings_completion_deadline_at": (now + timedelta(days=7)).isoformat(),
            },
            required_meetings=5,
        )
        await self.insert_entities([round_entity])

        result = await self.repo.get_running_round_id(self.session)

        self.assertEqual(result, round_entity.round_id)

    async def test_get_running_round_id_on_end_boundary(self):
        """Test returns round_id when meetings_completion_deadline_at is just after now (inclusive)."""
        now = datetime.now(timezone.utc)
        round_entity = MentorshipRoundEntity(
            name="end-boundary-round",
            description={
                "match_notification_at": (now - timedelta(days=7)).isoformat(),
                "meetings_completion_deadline_at": (now + timedelta(seconds=1)).isoformat(),
            },
            required_meetings=5,
        )
        await self.insert_entities([round_entity])

        result = await self.repo.get_running_round_id(self.session)

        self.assertEqual(result, round_entity.round_id)

    async def test_get_running_round_id_before_window(self):
        """Test returns None when now is before match_notification_at."""
        now = datetime.now(timezone.utc)
        round_entity = MentorshipRoundEntity(
            name="future-round",
            description={
                "match_notification_at": (now + timedelta(days=1)).isoformat(),
                "meetings_completion_deadline_at": (now + timedelta(days=7)).isoformat(),
            },
            required_meetings=5,
        )
        await self.insert_entities([round_entity])

        result = await self.repo.get_running_round_id(self.session)

        self.assertIsNone(result)

    async def test_get_running_round_id_after_window(self):
        """Test returns None when now is past meetings_completion_deadline_at."""
        now = datetime.now(timezone.utc)
        round_entity = MentorshipRoundEntity(
            name="past-round",
            description={
                "match_notification_at": (now - timedelta(days=7)).isoformat(),
                "meetings_completion_deadline_at": (now - timedelta(days=1)).isoformat(),
            },
            required_meetings=5,
        )
        await self.insert_entities([round_entity])

        result = await self.repo.get_running_round_id(self.session)

        self.assertIsNone(result)

    async def test_get_running_round_id_no_rounds(self):
        """Test returns None when no rounds exist."""
        result = await self.repo.get_running_round_id(self.session)

        self.assertIsNone(result)

    async def test_get_running_round_id_missing_date_fields(self):
        """Test returns None when description lacks the required date keys."""
        round_entity = MentorshipRoundEntity(
            name="no-dates-round",
            description={"goal": "no dates here"},
            required_meetings=5,
        )
        await self.insert_entities([round_entity])

        result = await self.repo.get_running_round_id(self.session)

        self.assertIsNone(result)

    async def test_get_running_round_id_null_date_values(self):
        """Test returns None when date keys exist but their values are JSON null."""
        round_entity = MentorshipRoundEntity(
            name="null-dates-round",
            description={
                "match_notification_at": None,
                "meetings_completion_deadline_at": None,
            },
            required_meetings=5,
        )
        await self.insert_entities([round_entity])

        result = await self.repo.get_running_round_id(self.session)

        self.assertIsNone(result)

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

    async def test_get_running_round_id_null_description(self):
        """Test returns None when description is null."""
        round_entity = MentorshipRoundEntity(
            name="null-description-round",
            description=None,
            required_meetings=5,
        )
        await self.insert_entities([round_entity])

        result = await self.repo.get_running_round_id(self.session)

        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
