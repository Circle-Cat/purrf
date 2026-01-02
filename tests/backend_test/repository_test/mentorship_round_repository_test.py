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


if __name__ == "__main__":
    unittest.main()
