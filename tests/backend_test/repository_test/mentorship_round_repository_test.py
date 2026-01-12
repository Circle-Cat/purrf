import unittest
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


if __name__ == "__main__":
    unittest.main()
