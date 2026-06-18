import unittest
import uuid
from datetime import datetime, timezone


from backend.repository.users_repository import UsersRepository
from backend.entity.users_entity import UsersEntity
from backend.entity.experience_entity import ExperienceEntity
from backend.common.mentorship_enums import CommunicationMethod
from tests.backend_test.repository_test.base_repository_test_lib import (
    BaseRepositoryTestLib,
)


class TestUsersRepository(BaseRepositoryTestLib):
    async def asyncSetUp(self):
        await super().asyncSetUp()

        # repo instance
        self.repo = UsersRepository()

        self.users = [
            UsersEntity(
                first_name="Alice",
                last_name="Admin",
                timezone="Asia/Shanghai",
                timezone_updated_at=datetime.now(timezone.utc),
                communication_channel=CommunicationMethod.EMAIL,
                primary_email="alice@example.com",
                is_active=True,
                updated_timestamp=datetime.now(timezone.utc),
                subject_identifier=str(uuid.uuid4()),
            ),
            UsersEntity(
                first_name="Bob",
                last_name="Smith",
                timezone="America/New_York",
                timezone_updated_at=datetime.now(timezone.utc),
                communication_channel=CommunicationMethod.EMAIL,
                primary_email="bob@example.com",
                alternative_emails=["b1@example.com", "b2@example.com"],
                is_active=True,
                updated_timestamp=datetime.now(timezone.utc),
                subject_identifier=str(uuid.uuid4()),
            ),
            UsersEntity(
                first_name="Charlie",
                last_name="Inactive",
                timezone="Asia/Shanghai",
                timezone_updated_at=datetime.now(timezone.utc),
                communication_channel=CommunicationMethod.EMAIL,
                primary_email="charlie@example.com",
                is_active=False,
                updated_timestamp=datetime.now(timezone.utc),
                subject_identifier=str(uuid.uuid4()),
            ),
        ]

        await self.insert_entities(self.users)

        self.user_entity = self.users[0]

        self.experiences = [
            ExperienceEntity(
                user_id=self.users[0].user_id,
                education=[{"school": "Harvard"}],
                work_history=[{"company": "OpenAI"}],
            ),
            ExperienceEntity(
                user_id=self.users[1].user_id,
                education=[{"school": "MIT"}],
                work_history=[{"company": "Google"}],
            ),
            # user 3 has no experience
        ]

        await self.insert_entities(self.experiences)

    async def test_get_all_by_ids_success(self):
        """Test fetching users in bulk with multiple valid user IDs."""
        user_ids = [self.users[0].user_id, self.users[1].user_id]

        users = await self.repo.get_all_by_ids(self.session, user_ids)

        self.assertEqual(len(users), 2)

        fetched_ids = [u.user_id for u in users]
        self.assertIn(self.users[0].user_id, fetched_ids)
        self.assertIn(self.users[1].user_id, fetched_ids)

    async def test_get_all_by_ids_partial_match(self):
        """Test behavior when some of the provided IDs do not exist."""
        user_ids = [self.users[0].user_id, 99999]

        users = await self.repo.get_all_by_ids(self.session, user_ids)

        self.assertEqual(len(users), 1)
        self.assertEqual(users[0].user_id, self.users[0].user_id)

    async def test_get_all_by_ids_empty_list(self):
        """Test behavior when an empty ID list is provided."""
        users = await self.repo.get_all_by_ids(self.session, [])
        self.assertEqual(users, [])

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

    async def test_get_user_by_subject_identifier(self):
        """Test retrieving an existing user by subject identifier"""
        user = await self.repo.get_user_by_subject_identifier(
            self.session, self.user_entity.subject_identifier
        )

        self.assertEqual(user, self.user_entity)

    async def test_get_user_by_subject_identifier_not_found(self):
        """Test retrieving a non-existent subject identifier returns None."""
        user = await self.repo.get_user_by_subject_identifier(self.session, "Sub1")
        self.assertIsNone(user)

        user = await self.repo.get_user_by_subject_identifier(
            self.session, "nonexistent"
        )
        self.assertIsNone(user)

    async def test_get_user_by_subject_identifier_is_None(self):
        """Test passing None as subject identifier returns None."""
        user = await self.repo.get_user_by_subject_identifier(self.session, None)
        self.assertIsNone(user)

        user = await self.repo.get_user_by_subject_identifier(self.session, "")
        self.assertIsNone(user)

    async def test_get_user_by_primary_email(self):
        """Test retrieving an existing user by primary email"""
        user = await self.repo.get_user_by_primary_email(
            self.session, self.user_entity.primary_email
        )

        self.assertEqual(user, self.user_entity)
        self.assertEqual(user.primary_email, self.user_entity.primary_email)

    async def test_get_user_by_primary_email_is_None(self):
        """Test passing None as subject identifier returns None."""
        user = await self.repo.get_user_by_primary_email(self.session, None)
        self.assertIsNone(user)

        user = await self.repo.get_user_by_primary_email(self.session, "")
        self.assertIsNone(user)

    async def test_get_user_by_primary_email_not_found(self):
        """Test retrieving a non-existent user by email returns None."""
        user = await self.repo.get_user_by_primary_email(
            self.session, "non-existent@example.com"
        )

        self.assertIsNone(user)

    async def test_upsert_users_insert_user_entity(self):
        """Test insert a new UserEntity"""
        new_user = UsersEntity(
            first_name="Dave",
            last_name="New",
            timezone="Asia/Shanghai",
            timezone_updated_at=datetime.now(timezone.utc),
            communication_channel="email",
            primary_email="dave@example.com",
            is_active=True,
            updated_timestamp=datetime.now(timezone.utc),
            subject_identifier="sub4",
        )

        user_in_db = await self.repo.get_user_by_subject_identifier(
            self.session, new_user.subject_identifier
        )
        self.assertIsNone(user_in_db)

        inserted_user = await self.repo.upsert_users(self.session, new_user)

        self.assertIsNotNone(inserted_user.user_id)

    async def test_upsert_users_update_user_entity(self):
        """Test update a existed UserEntity"""
        updated_entity = UsersEntity(
            user_id=self.user_entity.user_id,
            is_active=False,
        )
        user = await self.repo.upsert_users(self.session, updated_entity)

        self.assertFalse(user.is_active)
        self.assertEqual(user.subject_identifier, self.user_entity.subject_identifier)

    def _make_user(self, *, first_name="T", last_name="U", email):
        return UsersEntity(
            first_name=first_name,
            last_name=last_name,
            timezone="UTC",
            timezone_updated_at=datetime.now(timezone.utc),
            communication_channel=CommunicationMethod.EMAIL,
            primary_email=email,
            is_active=True,
            updated_timestamp=datetime.now(timezone.utc),
            subject_identifier=str(uuid.uuid4()),
        )

    async def test_list_users_search_matches_and_paginates(self):
        """A unique token isolates these rows from any pre-existing DB data."""
        token = uuid.uuid4().hex[:10]
        await self.insert_entities([
            self._make_user(first_name="Zoe", email=f"zoe-{token}@example.com"),
            self._make_user(first_name="Yan", email=f"yan-{token}@example.com"),
        ])

        page1, total = await self.repo.list_users(
            self.session, search=token, limit=1, offset=0
        )
        self.assertEqual(total, 2)
        self.assertEqual(len(page1), 1)

        page2, total2 = await self.repo.list_users(
            self.session, search=token, limit=1, offset=1
        )
        self.assertEqual(total2, 2)
        self.assertEqual(len(page2), 1)
        self.assertNotEqual(page1[0].user_id, page2[0].user_id)

    async def test_list_users_search_is_case_insensitive_over_name_and_email(self):
        token = uuid.uuid4().hex[:10]
        await self.insert_entities([
            self._make_user(first_name=f"Name{token}", email="byname@example.com"),
        ])
        by_name, total = await self.repo.list_users(self.session, search=token.upper())
        self.assertEqual(total, 1)
        self.assertEqual(by_name[0].first_name, f"Name{token}")

    async def test_set_super_admin_flips_flag(self):
        token = uuid.uuid4().hex[:10]
        users = [self._make_user(email=f"sa-{token}@example.com")]
        await self.insert_entities(users)
        user_id = users[0].user_id

        updated = await self.repo.set_super_admin(self.session, user_id, True)
        self.assertEqual(updated, 1)

        refetched = await self.repo.get_user_by_user_id(self.session, user_id)
        self.assertTrue(refetched.is_super_admin)

    async def test_set_super_admin_missing_user_updates_nothing(self):
        updated = await self.repo.set_super_admin(self.session, 9_999_999, True)
        self.assertEqual(updated, 0)


if __name__ == "__main__":
    unittest.main()
