import unittest
import uuid
from datetime import datetime, timezone

from backend.entity.users_entity import UsersEntity
from backend.common.recruiting_enums import UserType
from tests.backend_test.repository_test.base_repository_test_lib import (
    BaseRepositoryTestLib,
)


class TestUsersRecruitingFields(BaseRepositoryTestLib):
    async def test_insert_external_blocked_user(self):
        user = UsersEntity(
            first_name="Cand",
            last_name="Idate",
            timezone="America/Los_Angeles",
            timezone_updated_at=datetime.now(timezone.utc),
            primary_email="cand@example.com",
            is_active=False,
            updated_timestamp=datetime.now(timezone.utc),
            subject_identifier=str(uuid.uuid4()),
            user_type=UserType.EXTERNAL,
            is_blocked=True,
            blocked_reason="no-show",
        )
        await self.insert_entities([user])
        self.assertIsNotNone(user.user_id)
        self.assertEqual(user.user_type, UserType.EXTERNAL)
        self.assertTrue(user.is_blocked)
        self.assertEqual(user.blocked_reason, "no-show")

    async def test_communication_channel_nullable(self):
        user = UsersEntity(
            first_name="No",
            last_name="Channel",
            timezone="America/Los_Angeles",
            timezone_updated_at=datetime.now(timezone.utc),
            primary_email="nochan@example.com",
            is_active=False,
            updated_timestamp=datetime.now(timezone.utc),
            subject_identifier=str(uuid.uuid4()),
            user_type=UserType.EXTERNAL,
            communication_channel=None,
        )
        await self.insert_entities([user])
        self.assertIsNone(user.communication_channel)


if __name__ == "__main__":
    unittest.main()
