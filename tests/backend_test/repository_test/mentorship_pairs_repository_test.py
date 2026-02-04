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
    MentorActionStatus,
    MenteeActionStatus,
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
            MentorshipRoundEntity(
                name="2026-spring",
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
                mentor_action_status=MentorActionStatus.CONFIRMED,
                mentee_action_status=MenteeActionStatus.CONFIRMED,
                recommendation_reason="",
            ),
            MentorshipPairsEntity(
                round_id=self.rounds[1].round_id,
                mentor_id=self.users[0].user_id,
                mentee_id=self.users[1].user_id,
                completed_count=2,
                status=PairStatus.ACTIVE,
                mentor_action_status=MentorActionStatus.CONFIRMED,
                mentee_action_status=MenteeActionStatus.CONFIRMED,
                recommendation_reason="Mentor's area of expertise matches mentee's interests.",
            ),
            MentorshipPairsEntity(
                round_id=self.rounds[0].round_id,
                mentor_id=self.users[2].user_id,
                mentee_id=self.users[0].user_id,
                completed_count=3,
                status=PairStatus.ACTIVE,
                mentor_action_status=MentorActionStatus.PENDING,
                mentee_action_status=MenteeActionStatus.CONFIRMED,
                recommendation_reason="Confirmed partnership for next round",
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

    async def test_get_partner_ids_by_user_and_round(self):
        """Test passing both user_id and round_id returns the unique partner IDs."""
        result = await self.repo.get_partner_ids_by_user_and_round(
            self.session, self.users[0].user_id, self.rounds[0].round_id
        )

        self.assertIsNotNone(result)
        self.assertEqual(len(result), 2)
        self.assertIn(self.users[1].user_id, result)
        self.assertIn(self.users[2].user_id, result)

    async def test_get_partner_ids_by_user_and_round_by_user_non_existent(self):
        """Test passing non-existent user ID and valid rounds ID returns an empty collection."""
        result = await self.repo.get_partner_ids_by_user_and_round(
            self.session, 9999, self.rounds[0].round_id
        )

        self.assertIsNotNone(result)
        self.assertEqual(result, [])

    async def test_get_partner_ids_by_user_and_round_by_round_non_existent(self):
        """Test passing valid user ID and non-existent rounds ID returns an empty collection."""
        result = await self.repo.get_partner_ids_by_user_and_round(
            self.session, self.users[0].user_id, 9999
        )

        self.assertIsNotNone(result)
        self.assertEqual(result, [])

    async def test_upsert_pairs_insert(self):
        """Test insert a new mentorship pairs entity correctly."""
        pair = MentorshipPairsEntity(
            round_id=self.rounds[2].round_id,
            mentor_id=self.users[1].user_id,
            mentee_id=self.users[2].user_id,
            completed_count=0,
            status=PairStatus.ACTIVE,
            mentor_action_status=MentorActionStatus.PENDING,
            mentee_action_status=MenteeActionStatus.PENDING,
            recommendation_reason="Confirmed partnership for next round.",
        )

        result = await self.repo.upsert_pairs(self.session, pair)

        self.assertIsNotNone(result.pair_id)
        self.assertEqual(result.mentor_id, pair.mentor_id)
        self.assertEqual(result.mentee_id, pair.mentee_id)
        self.assertEqual(result.round_id, pair.round_id)

    async def test_upsert_pairs_update(self):
        """Test update an existing mentorship_pairs entity correctly."""
        pair = MentorshipPairsEntity(
            round_id=self.rounds[2].round_id,
            mentor_id=self.users[1].user_id,
            mentee_id=self.users[2].user_id,
            completed_count=1,
            status=PairStatus.ACTIVE,
            mentor_action_status=MentorActionStatus.CONFIRMED,
            mentee_action_status=MenteeActionStatus.CONFIRMED,
            recommendation_reason="Strong alignment in goals.",
            meeting_log={"Date": "Feb 27, 2026", "Time": "8:30 AM - 9:00 AM (CST)"},
        )

        result = await self.repo.upsert_pairs(self.session, pair)

        self.assertEqual(result.mentor_action_status, pair.mentor_action_status)
        self.assertEqual(result.mentee_action_status, pair.mentee_action_status)
        self.assertEqual(result.recommendation_reason, pair.recommendation_reason)
        self.assertEqual(result.meeting_log, pair.meeting_log)


if __name__ == "__main__":
    unittest.main()
