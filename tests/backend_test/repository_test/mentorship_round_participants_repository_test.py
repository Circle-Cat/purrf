import unittest
import uuid
from datetime import datetime, timezone

from backend.entity.mentorship_round_participants_entity import (
    MentorshipRoundParticipantsEntity,
)
from backend.entity.users_entity import UsersEntity
from backend.entity.mentorship_round_entity import MentorshipRoundEntity
from backend.repository.mentorship_round_participants_repository import (
    MentorshipRoundParticipantsRepository,
)
from backend.common.mentorship_enums import UserTimezone, CommunicationMethod
from tests.backend_test.repository_test.base_repository_test_lib import (
    BaseRepositoryTestLib,
)


class TestMentorshipRoundParticipantsRepository(BaseRepositoryTestLib):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.repo = MentorshipRoundParticipantsRepository()

        self.user = UsersEntity(
            first_name="Alice",
            last_name="Admin",
            timezone=UserTimezone.ASIA_SHANGHAI,
            timezone_updated_at=datetime.now(timezone.utc),
            communication_channel=CommunicationMethod.EMAIL,
            primary_email="alice@example.com",
            is_active=True,
            updated_timestamp=datetime.now(timezone.utc),
            subject_identifier=str(uuid.uuid4()),
        )

        await self.insert_entities([self.user])

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

        await self.insert_entities(self.rounds)

    async def test_get_by_user_id_and_round_id(self):
        """Test retrieve a mentorship round participants entity."""
        participants = [
            MentorshipRoundParticipantsEntity(
                user_id=self.user.user_id,
                round_id=self.rounds[0].round_id,
            ),
            MentorshipRoundParticipantsEntity(
                user_id=self.user.user_id,
                round_id=self.rounds[1].round_id,
            ),
        ]
        await self.insert_entities(participants)

        result = await self.repo.get_by_user_id_and_round_id(
            self.session, user_id=self.user.user_id, round_id=self.rounds[0].round_id
        )

        self.assertIsNotNone(result)
        self.assertEqual(result.user_id, self.user.user_id)
        self.assertEqual(result.round_id, self.rounds[0].round_id)

    async def test_get_by_user_id_and_round_id_empty(self):
        """Test retrieve none when the participants table is empty."""
        result = await self.repo.get_by_user_id_and_round_id(
            self.session, user_id=self.user.user_id, round_id=self.rounds[0].round_id
        )

        self.assertIsNone(result)

    async def test_get_by_user_id_and_round_id_not_found(self):
        """Test retrieve none when participants exist but none match the given IDs."""
        participant = MentorshipRoundParticipantsEntity(
            user_id=self.user.user_id,
            round_id=self.rounds[0].round_id,
        )
        await self.insert_entities([participant])

        result = await self.repo.get_by_user_id_and_round_id(
            self.session, user_id=self.user.user_id, round_id=self.rounds[1].round_id
        )

        self.assertIsNone(result)

    async def test_get_recent_participant_by_user_id(self):
        """Ensure the most recent participant is returned."""
        participants = [
            MentorshipRoundParticipantsEntity(
                user_id=self.user.user_id,
                round_id=self.rounds[0].round_id,
            ),
            MentorshipRoundParticipantsEntity(
                user_id=self.user.user_id,
                round_id=self.rounds[1].round_id,
            ),
        ]
        await self.insert_entities(participants)

        result = await self.repo.get_recent_participant_by_user_id(
            self.session, user_id=self.user.user_id
        )

        self.assertIsNotNone(result)
        self.assertEqual(
            result.round_id,
            max(self.rounds[0].round_id, self.rounds[1].round_id),
        )

    async def test_get_recent_participant_by_user_id_empty(self):
        """Should return None if the user has no participant records."""
        result = await self.repo.get_recent_participant_by_user_id(
            self.session, user_id=self.user.user_id
        )

        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
