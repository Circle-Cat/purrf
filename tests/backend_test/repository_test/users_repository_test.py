import unittest
from datetime import datetime

from backend.repository.users_repository import UsersRepository
from backend.entity.users_entity import UsersEntity
from backend.common.mentorship_enums import UserTimezone
from tests.backend_test.repository_test.base_repository_test_lib import (
    BaseRepositoryTestLib,
)


class TestUsersRepository(BaseRepositoryTestLib):
    async def asyncSetUp(self):
        await super().asyncSetUp()

        # repo instance
        self.repo = UsersRepository()

        # Insert test data
        self.user_entity = UsersEntity(
            user_id=1,
            first_name="Alice",
            last_name="Admin",
            timezone=UserTimezone.Asia_Shanghai,
            communication_channel="email",
            primary_email="alice@example.com",
            is_active=True,
            updated_timestamp=datetime.utcnow(),
            subject_identifier="sub1",
        )

        await self.insert_entities([self.user_entity])

    async def test_get_user_by_user_id(self):
        """Test retrieving an existing user by user ID."""
        user = await self.repo.get_user_by_user_id(
            self.session, self.user_entity.user_id
        )

        self.assertEqual(user, self.user_entity)

    async def test_get_user_by_user_id_not_found(self):
        """Test retrieving a non-existent user returns None."""
        user = await self.repo.get_user_by_user_id(self.session, 999)

        self.assertIsNone(user)

    async def test_get_user_by_user_id_is_None(self):
        """Test passing None as user_id returns None."""
        user = await self.repo.get_user_by_user_id(self.session, None)

        self.assertIsNone(user)


if __name__ == "__main__":
    unittest.main()
