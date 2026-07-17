import unittest
import uuid
from datetime import datetime, timezone


from backend.repository.users_repository import UsersRepository
from backend.entity.users_entity import UsersEntity
from backend.entity.experience_entity import ExperienceEntity
from backend.entity.user_identities_entity import UserIdentitiesEntity
from backend.entity.user_emails_entity import UserEmailsEntity
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
            ),
            UsersEntity(
                first_name="Bob",
                last_name="Smith",
                timezone="America/New_York",
                timezone_updated_at=datetime.now(timezone.utc),
                communication_channel=CommunicationMethod.EMAIL,
                primary_email="bob@example.com",
                is_active=True,
                updated_timestamp=datetime.now(timezone.utc),
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

    async def test_update_primary_email(self):
        """update_primary_email overwrites the column for the given user only."""
        await self.repo.update_primary_email(
            self.session, self.user_entity.user_id, "alice.new@example.com"
        )

        updated = await self.repo.get_user_by_user_id(
            self.session, self.user_entity.user_id
        )
        self.assertEqual(updated.primary_email, "alice.new@example.com")
        # other users untouched
        other = await self.repo.get_user_by_user_id(self.session, self.users[1].user_id)
        self.assertEqual(other.primary_email, "bob@example.com")

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
        )

        user_in_db = await self.repo.get_user_by_primary_email(
            self.session, new_user.primary_email
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

    def _make_user(self, *, first_name="T", last_name=None, email):
        # last_name defaults to the email's local part so tests that isolate
        # their rows with a token-bearing email still match search=token via
        # the name leg: the email leg of the search reads user_emails now,
        # not the legacy users.primary_email column this helper fills.
        return UsersEntity(
            first_name=first_name,
            last_name=last_name if last_name is not None else email.split("@")[0],
            timezone="UTC",
            timezone_updated_at=datetime.now(timezone.utc),
            communication_channel=CommunicationMethod.EMAIL,
            primary_email=email,
            is_active=True,
            updated_timestamp=datetime.now(timezone.utc),
        )

    async def test_list_users_search_matches_and_paginates(self):
        """A unique token isolates these rows from any pre-existing DB data.
        The token appears only in user_emails rows — the email leg of the
        search reads user_emails, not the legacy users.primary_email column."""
        token = uuid.uuid4().hex[:10]
        users = [
            self._make_user(first_name="Zoe", email=f"{uuid.uuid4()}@example.com"),
            self._make_user(first_name="Yan", email=f"{uuid.uuid4()}@example.com"),
        ]
        await self.insert_entities(users)
        await self.insert_entities([
            UserEmailsEntity(
                user_id=users[0].user_id,
                email=f"zoe-{token}@example.com",
                otp_confirmed=False,
                is_primary=False,
            ),
            UserEmailsEntity(
                user_id=users[1].user_id,
                email=f"yan-{token}@example.com",
                otp_confirmed=False,
                is_primary=False,
            ),
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
        self.assertNotEqual(page1[0][0].user_id, page2[0][0].user_id)

    async def test_list_users_search_is_case_insensitive_over_name_and_email(self):
        token = uuid.uuid4().hex[:10]
        await self.insert_entities([
            self._make_user(first_name=f"Name{token}", email="byname@example.com"),
        ])
        by_name, total = await self.repo.list_users(self.session, search=token.upper())
        self.assertEqual(total, 1)
        self.assertEqual(by_name[0][0].first_name, f"Name{token}")

    async def test_list_users_user_id_filters_to_exact_match(self):
        token = uuid.uuid4().hex[:10]
        target = self._make_user(
            first_name=f"Target{token}", email=f"target-{token}@example.com"
        )
        other = self._make_user(
            first_name=f"Other{token}", email=f"other-{token}@example.com"
        )
        await self.insert_entities([target, other])

        rows, total = await self.repo.list_users(self.session, user_id=target.user_id)
        self.assertEqual(total, 1)
        self.assertEqual(rows[0][0].user_id, target.user_id)

    async def test_list_users_user_id_combines_with_search(self):
        token = uuid.uuid4().hex[:10]
        match = self._make_user(
            first_name=f"Name{token}", email=f"m-{token}@example.com"
        )
        await self.insert_entities([match])

        # user_id matches but search does not -> no rows (filters are ANDed).
        rows, total = await self.repo.list_users(
            self.session, user_id=match.user_id, search="no-such-token-xyz"
        )
        self.assertEqual(total, 0)
        self.assertEqual(rows, [])

    async def test_list_users_internal_flag_true_when_has_internal_identity(self):
        token = uuid.uuid4().hex[:10]
        user = self._make_user(email=f"internal-{token}@example.com")
        await self.insert_entities([user])
        await self.insert_entities([
            UserIdentitiesEntity(
                user_id=user.user_id,
                subject_identifier=f"google-oauth2|{token}",
                identity_type="internal",
                email_claim=f"internal-{token}@circlecat.org",
            )
        ])

        rows, total = await self.repo.list_users(
            self.session, search=token, limit=10, offset=0
        )
        self.assertEqual(total, 1)
        entity, is_internal = rows[0]
        self.assertEqual(entity.user_id, user.user_id)
        self.assertTrue(is_internal)

    async def test_list_users_internal_flag_false_when_no_internal_identity(self):
        token = uuid.uuid4().hex[:10]
        user = self._make_user(email=f"external-{token}@example.com")
        await self.insert_entities([user])
        await self.insert_entities([
            UserIdentitiesEntity(
                user_id=user.user_id,
                subject_identifier=f"email|{token}",
                identity_type="external",
                email_claim=f"external-{token}@gmail.com",
            )
        ])

        rows, total = await self.repo.list_users(
            self.session, search=token, limit=10, offset=0
        )
        self.assertEqual(total, 1)
        _, is_internal = rows[0]
        self.assertFalse(is_internal)

    async def test_list_users_internal_flag_false_when_no_identities(self):
        token = uuid.uuid4().hex[:10]
        user = self._make_user(email=f"noident-{token}@example.com")
        await self.insert_entities([user])

        rows, total = await self.repo.list_users(
            self.session, search=token, limit=10, offset=0
        )
        self.assertEqual(total, 1)
        _, is_internal = rows[0]
        self.assertFalse(is_internal)

    async def test_list_users_preferred_name_carried_through(self):
        token = uuid.uuid4().hex[:10]
        user = self._make_user(email=f"pref-{token}@example.com")
        user.preferred_name = "Zoe Preferred"
        await self.insert_entities([user])

        rows, total = await self.repo.list_users(
            self.session, search=token, limit=10, offset=0
        )
        self.assertEqual(total, 1)
        entity, _ = rows[0]
        self.assertEqual(entity.preferred_name, "Zoe Preferred")

    async def test_list_users_preferred_name_none(self):
        token = uuid.uuid4().hex[:10]
        user = self._make_user(email=f"nopref-{token}@example.com")
        # preferred_name not set → defaults to None
        await self.insert_entities([user])

        rows, _ = await self.repo.list_users(
            self.session, search=token, limit=10, offset=0
        )
        entity, _ = rows[0]
        self.assertIsNone(entity.preferred_name)

    async def test_is_internal_true_when_has_internal_identity(self):
        token = uuid.uuid4().hex[:10]
        user = self._make_user(email=f"isint-{token}@example.com")
        await self.insert_entities([user])
        await self.insert_entities([
            UserIdentitiesEntity(
                user_id=user.user_id,
                subject_identifier=f"google-oauth2|isint-{token}",
                identity_type="internal",
                email_claim=f"isint-{token}@circlecat.org",
            )
        ])
        result = await self.repo.is_internal(self.session, user.user_id)
        self.assertTrue(result)

    async def test_is_internal_false_when_only_external_identity(self):
        token = uuid.uuid4().hex[:10]
        user = self._make_user(email=f"isext-{token}@example.com")
        await self.insert_entities([user])
        await self.insert_entities([
            UserIdentitiesEntity(
                user_id=user.user_id,
                subject_identifier=f"email|isext-{token}",
                identity_type="external",
                email_claim=f"isext-{token}@gmail.com",
            )
        ])
        result = await self.repo.is_internal(self.session, user.user_id)
        self.assertFalse(result)

    async def test_is_internal_false_when_no_identities(self):
        token = uuid.uuid4().hex[:10]
        user = self._make_user(email=f"isnone-{token}@example.com")
        await self.insert_entities([user])
        result = await self.repo.is_internal(self.session, user.user_id)
        self.assertFalse(result)

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

    async def test_list_blocked_users_returns_only_blocked(self):
        token = uuid.uuid4().hex[:10]
        blocked = self._make_user(
            first_name=f"Blocked{token}", email=f"blocked-{token}@example.com"
        )
        blocked.is_blocked = True
        blocked.blocked_by = 1
        blocked.blocked_at = datetime.now(timezone.utc)
        blocked.blocked_reason = "cheated"
        not_blocked = self._make_user(
            first_name=f"Clean{token}", email=f"clean-{token}@example.com"
        )
        await self.insert_entities([blocked, not_blocked])

        rows = await self.repo.list_blocked_users(self.session)
        ids = {u.user_id for u in rows}
        self.assertIn(blocked.user_id, ids)
        self.assertNotIn(not_blocked.user_id, ids)

    async def test_list_blocked_users_search_matches_name(self):
        token = uuid.uuid4().hex[:10]
        user = self._make_user(
            first_name=f"Name{token}", email=f"n-{token}@example.com"
        )
        user.is_blocked = True
        user.blocked_reason = "spam"
        await self.insert_entities([user])

        rows = await self.repo.list_blocked_users(self.session, search=token)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].user_id, user.user_id)

    async def test_list_blocked_users_search_matches_email(self):
        # The token appears only in a user_emails row — the email leg of the
        # search reads user_emails, not the legacy users.primary_email column.
        token = uuid.uuid4().hex[:10]
        user = self._make_user(email=f"{uuid.uuid4()}@example.com")
        user.is_blocked = True
        user.blocked_reason = "spam"
        await self.insert_entities([user])
        await self.insert_entities([
            UserEmailsEntity(
                user_id=user.user_id,
                email=f"findme-{token}@example.com",
                otp_confirmed=True,
                is_primary=True,
            )
        ])

        rows = await self.repo.list_blocked_users(self.session, search=token)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].user_id, user.user_id)

    async def test_list_blocked_users_search_matches_reason_case_insensitive(self):
        token = uuid.uuid4().hex[:10]
        user = self._make_user(email=f"reason-{token}@example.com")
        user.is_blocked = True
        user.blocked_reason = f"Fraud-{token}"
        await self.insert_entities([user])

        rows = await self.repo.list_blocked_users(self.session, search=token.upper())
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].user_id, user.user_id)

    async def test_list_blocked_users_search_with_no_match_is_empty(self):
        rows = await self.repo.list_blocked_users(
            self.session, search="no-such-token-xyz"
        )
        self.assertEqual(rows, [])

    async def test_clear_block_resets_all_block_columns(self):
        token = uuid.uuid4().hex[:10]
        user = self._make_user(email=f"clear-{token}@example.com")
        user.is_blocked = True
        user.blocked_by = 1
        user.blocked_at = datetime.now(timezone.utc)
        user.blocked_reason = "test"
        await self.insert_entities([user])

        await self.repo.clear_block(self.session, user.user_id)

        refetched = await self.repo.get_user_by_user_id(self.session, user.user_id)
        self.assertFalse(refetched.is_blocked)
        self.assertIsNone(refetched.blocked_by)
        self.assertIsNone(refetched.blocked_at)
        self.assertIsNone(refetched.blocked_reason)

    async def test_clear_block_on_non_blocked_user_is_a_noop_success(self):
        token = uuid.uuid4().hex[:10]
        user = self._make_user(email=f"already-clean-{token}@example.com")
        await self.insert_entities([user])

        await self.repo.clear_block(self.session, user.user_id)  # must not raise

        refetched = await self.repo.get_user_by_user_id(self.session, user.user_id)
        self.assertFalse(refetched.is_blocked)

    async def test_clear_block_missing_user_is_a_noop_success(self):
        await self.repo.clear_block(self.session, 9_999_999)  # must not raise

    async def test_get_users_and_emails_empty_list(self):
        users_map, emails_map = await self.repo.get_users_and_emails_by_ids(
            self.session, []
        )
        self.assertEqual(users_map, {})
        self.assertEqual(emails_map, {})

    async def test_get_users_and_emails_unknown_id(self):
        users_map, emails_map = await self.repo.get_users_and_emails_by_ids(
            self.session, [999]
        )
        self.assertEqual(users_map, {})
        self.assertEqual(emails_map, {})

    async def test_get_users_and_emails_no_emails(self):
        users_map, emails_map = await self.repo.get_users_and_emails_by_ids(
            self.session, [self.users[0].user_id]
        )
        self.assertIn(self.users[0].user_id, users_map)
        self.assertEqual(emails_map[self.users[0].user_id], [])

    async def test_get_users_and_emails_with_email(self):
        await self.insert_entities([
            UserEmailsEntity(
                user_id=self.users[0].user_id,
                email="alice@work.com",
                otp_confirmed=True,
                is_primary=True,
            )
        ])
        _, emails_map = await self.repo.get_users_and_emails_by_ids(
            self.session, [self.users[0].user_id]
        )
        self.assertEqual(
            {e.email for e in emails_map[self.users[0].user_id]},
            {"alice@work.com"},
        )

    async def test_get_users_and_emails_multiple_users(self):
        await self.insert_entities([
            UserEmailsEntity(
                user_id=self.users[0].user_id,
                email="alice1@work.com",
                otp_confirmed=True,
                is_primary=True,
            ),
            UserEmailsEntity(
                user_id=self.users[0].user_id,
                email="alice2@work.com",
                otp_confirmed=True,
                is_primary=False,
            ),
            UserEmailsEntity(
                user_id=self.users[1].user_id,
                email="bob@work.com",
                otp_confirmed=True,
                is_primary=True,
            ),
        ])
        user_ids = [self.users[0].user_id, self.users[1].user_id]
        users_map, emails_map = await self.repo.get_users_and_emails_by_ids(
            self.session, user_ids
        )
        self.assertEqual(
            set(users_map.keys()), {self.users[0].user_id, self.users[1].user_id}
        )
        self.assertEqual(
            {e.email for e in emails_map[self.users[0].user_id]},
            {"alice1@work.com", "alice2@work.com"},
        )
        self.assertEqual(
            {e.email for e in emails_map[self.users[1].user_id]},
            {"bob@work.com"},
        )

    # ------------------------------------------------------------------
    # sort / filter tests
    # ------------------------------------------------------------------

    async def test_list_users_sort_by_last_name_desc(self):
        """sort_by='last_name', order='desc' returns users in descending last_name
        order (with user_id as tiebreaker)."""
        token = uuid.uuid4().hex[:10]
        users = [
            self._make_user(last_name=f"Zebra-{token}", email=f"z-{token}@example.com"),
            self._make_user(last_name=f"Apple-{token}", email=f"a-{token}@example.com"),
            self._make_user(last_name=f"Mango-{token}", email=f"m-{token}@example.com"),
        ]
        await self.insert_entities(users)

        rows, total = await self.repo.list_users(
            self.session,
            search=token,
            sort_by="last_name",
            order="desc",
        )
        self.assertEqual(total, 3)
        last_names = [r[0].last_name for r in rows]
        self.assertEqual(
            last_names,
            sorted(last_names, reverse=True),
            msg=f"Expected descending last_name, got {last_names}",
        )

    async def test_list_users_sort_by_last_name_asc_default(self):
        """sort_by='last_name' without order defaults to ascending."""
        token = uuid.uuid4().hex[:10]
        users = [
            self._make_user(
                last_name=f"Zebra-{token}", email=f"z2-{token}@example.com"
            ),
            self._make_user(
                last_name=f"Apple-{token}", email=f"a2-{token}@example.com"
            ),
        ]
        await self.insert_entities(users)

        rows, total = await self.repo.list_users(
            self.session,
            search=token,
            sort_by="last_name",
            order="asc",
        )
        self.assertEqual(total, 2)
        last_names = [r[0].last_name for r in rows]
        self.assertEqual(last_names, sorted(last_names))

    async def test_list_users_default_order_is_by_user_id(self):
        """No sort_by → deterministic ascending user_id order."""
        token = uuid.uuid4().hex[:10]
        users = [
            self._make_user(
                last_name=f"Zebra-{token}", email=f"d1-{token}@example.com"
            ),
            self._make_user(
                last_name=f"Apple-{token}", email=f"d2-{token}@example.com"
            ),
            self._make_user(
                last_name=f"Mango-{token}", email=f"d3-{token}@example.com"
            ),
        ]
        await self.insert_entities(users)

        rows, total = await self.repo.list_users(self.session, search=token)
        self.assertEqual(total, 3)
        ids = [r[0].user_id for r in rows]
        self.assertEqual(
            ids, sorted(ids), msg="Default order should be ascending user_id"
        )

    async def test_list_users_unknown_sort_by_falls_back_to_user_id(self):
        """An unknown sort_by value silently falls back to user_id order."""
        token = uuid.uuid4().hex[:10]
        users = [
            self._make_user(email=f"unk1-{token}@example.com"),
            self._make_user(email=f"unk2-{token}@example.com"),
        ]
        await self.insert_entities(users)

        rows, total = await self.repo.list_users(
            self.session, search=token, sort_by="nonexistent_column"
        )
        self.assertEqual(total, 2)
        ids = [r[0].user_id for r in rows]
        self.assertEqual(ids, sorted(ids))

    async def test_list_users_filter_is_super_admin_true(self):
        """is_super_admin=True returns only super-admins; total reflects the filter."""
        token = uuid.uuid4().hex[:10]
        super_user = self._make_user(email=f"sup-{token}@example.com")
        regular_user = self._make_user(email=f"reg-{token}@example.com")
        await self.insert_entities([super_user, regular_user])
        await self.repo.set_super_admin(self.session, super_user.user_id, True)

        rows, total = await self.repo.list_users(
            self.session, search=token, is_super_admin=True
        )
        self.assertEqual(total, 1)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0].user_id, super_user.user_id)
        self.assertTrue(rows[0][0].is_super_admin)

    async def test_list_users_filter_is_super_admin_false(self):
        """is_super_admin=False returns only non-super-admins."""
        token = uuid.uuid4().hex[:10]
        super_user = self._make_user(email=f"sup2-{token}@example.com")
        regular_user = self._make_user(email=f"reg2-{token}@example.com")
        await self.insert_entities([super_user, regular_user])
        await self.repo.set_super_admin(self.session, super_user.user_id, True)

        rows, total = await self.repo.list_users(
            self.session, search=token, is_super_admin=False
        )
        self.assertEqual(total, 1)
        self.assertEqual(rows[0][0].user_id, regular_user.user_id)
        self.assertFalse(rows[0][0].is_super_admin)

    async def test_list_users_filter_user_type_internal(self):
        """user_type='internal' returns only users with an internal identity."""
        token = uuid.uuid4().hex[:10]
        internal_user = self._make_user(email=f"int-{token}@example.com")
        external_user = self._make_user(email=f"ext-{token}@example.com")
        no_identity_user = self._make_user(email=f"none-{token}@example.com")
        await self.insert_entities([internal_user, external_user, no_identity_user])
        await self.insert_entities([
            UserIdentitiesEntity(
                user_id=internal_user.user_id,
                subject_identifier=f"google-oauth2|int-{token}",
                identity_type="internal",
                email_claim=f"int-{token}@circlecat.org",
            ),
            UserIdentitiesEntity(
                user_id=external_user.user_id,
                subject_identifier=f"email|ext-{token}",
                identity_type="external",
                email_claim=f"ext-{token}@gmail.com",
            ),
        ])

        rows, total = await self.repo.list_users(
            self.session, search=token, user_type="internal"
        )
        self.assertEqual(total, 1)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0].user_id, internal_user.user_id)
        self.assertTrue(rows[0][1])  # is_internal flag

    async def test_list_users_filter_user_type_external(self):
        """user_type='external' returns only users WITHOUT an internal identity."""
        token = uuid.uuid4().hex[:10]
        internal_user = self._make_user(email=f"int2-{token}@example.com")
        external_user = self._make_user(email=f"ext2-{token}@example.com")
        no_identity_user = self._make_user(email=f"none2-{token}@example.com")
        await self.insert_entities([internal_user, external_user, no_identity_user])
        await self.insert_entities([
            UserIdentitiesEntity(
                user_id=internal_user.user_id,
                subject_identifier=f"google-oauth2|int2-{token}",
                identity_type="internal",
                email_claim=f"int2-{token}@circlecat.org",
            ),
            UserIdentitiesEntity(
                user_id=external_user.user_id,
                subject_identifier=f"email|ext2-{token}",
                identity_type="external",
                email_claim=f"ext2-{token}@gmail.com",
            ),
        ])

        rows, total = await self.repo.list_users(
            self.session, search=token, user_type="external"
        )
        self.assertEqual(total, 2)
        returned_ids = {r[0].user_id for r in rows}
        self.assertIn(external_user.user_id, returned_ids)
        self.assertIn(no_identity_user.user_id, returned_ids)
        self.assertNotIn(internal_user.user_id, returned_ids)
        # none of the returned rows should have is_internal=True
        for row in rows:
            self.assertFalse(row[1])

    async def test_list_users_sort_by_user_type(self):
        """sort_by='user_type' orders by the derived internal/external flag:
        ascending lists external (no internal identity) before internal."""
        token = uuid.uuid4().hex[:10]
        internal_user = self._make_user(email=f"sint-{token}@example.com")
        external_user = self._make_user(email=f"sext-{token}@example.com")
        await self.insert_entities([internal_user, external_user])
        await self.insert_entities([
            UserIdentitiesEntity(
                user_id=internal_user.user_id,
                subject_identifier=f"google-oauth2|sint-{token}",
                identity_type="internal",
                email_claim=f"sint-{token}@circlecat.org",
            ),
        ])

        asc_rows, _ = await self.repo.list_users(
            self.session, search=token, sort_by="user_type", order="asc"
        )
        self.assertEqual(
            [r[0].user_id for r in asc_rows],
            [external_user.user_id, internal_user.user_id],
            msg="asc should list external before internal",
        )

        desc_rows, _ = await self.repo.list_users(
            self.session, search=token, sort_by="user_type", order="desc"
        )
        self.assertEqual(
            [r[0].user_id for r in desc_rows],
            [internal_user.user_id, external_user.user_id],
            msg="desc should list internal before external",
        )

    async def test_get_super_admins_returns_only_flagged_users(self):
        """get_super_admins returns exactly the users with is_super_admin True."""
        super_admin = UsersEntity(
            first_name="Sa",
            last_name="Admin",
            timezone="UTC",
            timezone_updated_at=datetime.now(timezone.utc),
            communication_channel=CommunicationMethod.EMAIL,
            primary_email=f"superadmin-{uuid.uuid4().hex}@example.com",
            is_active=True,
            is_super_admin=True,
            updated_timestamp=datetime.now(timezone.utc),
        )
        await self.insert_entities([super_admin])

        result = await self.repo.get_super_admins(self.session)

        ids = {u.user_id for u in result}
        self.assertIn(super_admin.user_id, ids)
        # The non-super-admin users from setUp must not be returned.
        self.assertNotIn(self.users[0].user_id, ids)
        self.assertTrue(all(u.is_super_admin for u in result))


if __name__ == "__main__":
    unittest.main()
