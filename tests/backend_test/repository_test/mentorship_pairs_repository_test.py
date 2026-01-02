import unittest
import uuid
from datetime import datetime, timezone
from backend.entity.mentorship_pairs_entity import MentorshipPairsEntity
from backend.entity.mentorship_round_entity import MentorshipRoundEntity
from backend.entity.users_entity import UsersEntity
from backend.repository.mentorship_pairs_repository import MentorshipPairsRepository
from tests.backend_test.repository_test.base_repository_test_lib import (
    BaseRepositoryTestLib,
)
from backend.common.mentorship_enums import (
    PairStatus,
    UserTimezone,
    CommunicationMethod,
)


class TestMentorShipPairsRepository(BaseRepositoryTestLib):
    async def asyncSetUp(self):
        await super().asyncSetUp()

        self.repo = MentorshipPairsRepository()

        self.now = datetime.now(timezone.utc)

        self.users = [
            UsersEntity(
                first_name="Alice",
                last_name="Admin",
                timezone=UserTimezone.ASIA_SHANGHAI,
                timezone_updated_at=self.now,
                communication_channel=CommunicationMethod.EMAIL,
                primary_email="alice@example.com",
                is_active=True,
                updated_timestamp=self.now,
                subject_identifier=str(uuid.uuid4()),
            ),
            UsersEntity(
                first_name="Bob",
                last_name="Smith",
                timezone=UserTimezone.AMERICA_NEW_YORK,
                timezone_updated_at=self.now,
                communication_channel=CommunicationMethod.EMAIL,
                primary_email="bob@example.com",
                is_active=True,
                updated_timestamp=self.now,
                subject_identifier=str(uuid.uuid4()),
            ),
            UsersEntity(
                first_name="Charlie",
                last_name="Inactive",
                timezone=UserTimezone.ASIA_SHANGHAI,
                timezone_updated_at=self.now,
                communication_channel=CommunicationMethod.EMAIL,
                primary_email="charlie@example.com",
                is_active=False,
                updated_timestamp=self.now,
                subject_identifier=str(uuid.uuid4()),
            ),
        ]

        await self.insert_entities(self.users)

        self.rounds = [
            MentorshipRoundEntity(
                name="2025-spring",
                required_meetings=5,
            ),
            MentorshipRoundEntity(
                name="2025-fall",
                required_meetings=5,
            ),
        ]

        await self.insert_entities(self.rounds)

        self.pairs = [
            MentorshipPairsEntity(
                round_id=self.rounds[0].round_id,
                mentor_id=self.users[0].user_id,
                mentee_id=self.users[1].user_id,
                completed_count=5,
                status=PairStatus.ACTIVE,
            ),
            MentorshipPairsEntity(
                round_id=self.rounds[1].round_id,
                mentor_id=self.users[0].user_id,
                mentee_id=self.users[1].user_id,
                completed_count=2,
                status=PairStatus.ACTIVE,
            ),
            MentorshipPairsEntity(
                round_id=self.rounds[0].round_id,
                mentor_id=self.users[2].user_id,
                mentee_id=self.users[0].user_id,
                completed_count=3,
                status=PairStatus.ACTIVE,
            ),
        ]

        await self.insert_entities(self.pairs)

    async def test_get_pairs_by_user_id_existing(self):
        """Test passing a valid user ID returns unique partner IDs."""
        result = await self.repo.get_all_partner_ids(
            self.session, self.users[0].user_id
        )

        self.assertIsNotNone(result)
        self.assertEqual(len(result), 2)
        self.assertIn(self.users[1].user_id, result)
        self.assertIn(self.users[2].user_id, result)

    async def test_get_pairs_by_user_non_existent(self):
        """Test passing a non-existent user ID returns an empty collection."""
        result = await self.repo.get_all_partner_ids(self.session, 9999)

        self.assertIsNotNone(result)
        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
