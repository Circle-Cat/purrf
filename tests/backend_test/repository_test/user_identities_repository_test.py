import unittest
import uuid
from datetime import datetime, timezone

from backend.repository.user_identities_repository import UserIdentitiesRepository
from backend.entity.users_entity import UsersEntity
from backend.entity.user_identities_entity import UserIdentitiesEntity
from backend.common.mentorship_enums import CommunicationMethod
from tests.backend_test.repository_test.base_repository_test_lib import (
    BaseRepositoryTestLib,
)


def _make_user() -> UsersEntity:
    return UsersEntity(
        first_name="Alice",
        last_name="Admin",
        timezone="Asia/Shanghai",
        timezone_updated_at=datetime.now(timezone.utc),
        communication_channel=CommunicationMethod.EMAIL,
        primary_email=f"{uuid.uuid4()}@example.com",
        is_active=True,
        updated_timestamp=datetime.now(timezone.utc),
        subject_identifier=str(uuid.uuid4()),
    )


class TestUserIdentitiesRepository(BaseRepositoryTestLib):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.repo = UserIdentitiesRepository()

        self.user = _make_user()
        await self.insert_entities([self.user])

        self.t1 = datetime(2024, 1, 1, tzinfo=timezone.utc)
        self.t2 = datetime(2024, 6, 1, tzinfo=timezone.utc)

    # get_user_and_login_state_by_sub — single JOIN for the hot auth path
    async def test_get_user_and_login_state_by_sub_hit(self):
        identity = UserIdentitiesEntity(
            user_id=self.user.user_id,
            subject_identifier="google-oauth2|join",
            identity_type="external",
            email_claim="alice@example.com",
            last_login_at=self.t1,
        )
        await self.insert_entities([identity])

        found = await self.repo.get_user_and_login_state_by_sub(
            self.session, "google-oauth2|join"
        )
        self.assertIsNotNone(found)
        user, identity_id, last_login_at = found
        self.assertEqual(user.user_id, self.user.user_id)
        self.assertEqual(user.is_active, self.user.is_active)
        self.assertEqual(identity_id, identity.identity_id)
        self.assertEqual(last_login_at, self.t1)

    async def test_get_user_and_login_state_by_sub_not_found(self):
        found = await self.repo.get_user_and_login_state_by_sub(
            self.session, "missing|x"
        )
        self.assertIsNone(found)

    # find_swappable_by_email — only matches mock (manual|) rows
    async def test_find_swappable_by_email_matches_manual_row(self):
        manual = UserIdentitiesEntity(
            user_id=self.user.user_id,
            subject_identifier="manual|alice@example.com",
            identity_type="external",
            email_claim="alice@example.com",
        )
        await self.insert_entities([manual])

        found = await self.repo.find_swappable_by_email(
            self.session, email_claim="alice@example.com"
        )
        self.assertIsNotNone(found)
        self.assertEqual(found.identity_id, manual.identity_id)

    async def test_find_swappable_by_email_ignores_real_sub_row(self):
        """A real (already-linked) sub sharing the email_claim is NOT returned."""
        real = UserIdentitiesEntity(
            user_id=self.user.user_id,
            subject_identifier="google-oauth2|abc",
            identity_type="external",
            email_claim="alice@example.com",
        )
        await self.insert_entities([real])

        found = await self.repo.find_swappable_by_email(
            self.session, email_claim="alice@example.com"
        )
        self.assertIsNone(found)

    async def test_find_swappable_by_email_not_found(self):
        found = await self.repo.find_swappable_by_email(
            self.session, email_claim="nobody@example.com"
        )
        self.assertIsNone(found)

    # upsert_identity
    async def test_upsert_identity_insert(self):
        identity = UserIdentitiesEntity(
            user_id=self.user.user_id,
            subject_identifier="email|new",
            identity_type="external",
            email_claim="alice@example.com",
        )
        merged = await self.repo.upsert_identity(self.session, identity)
        self.assertIsNotNone(merged.identity_id)

    async def test_upsert_identity_update(self):
        identity = UserIdentitiesEntity(
            user_id=self.user.user_id,
            subject_identifier="manual|alice@example.com",
            identity_type="external",
            email_claim="alice@example.com",
        )
        await self.insert_entities([identity])

        identity.subject_identifier = "google-oauth2|abc"
        merged = await self.repo.upsert_identity(self.session, identity)

        self.assertEqual(merged.identity_id, identity.identity_id)
        self.assertEqual(merged.subject_identifier, "google-oauth2|abc")

    # update_last_login — only-if-newer guard
    async def test_update_last_login_sets_when_null(self):
        identity = UserIdentitiesEntity(
            user_id=self.user.user_id,
            subject_identifier="email|null",
            identity_type="external",
            email_claim="alice@example.com",
            last_login_at=None,
        )
        await self.insert_entities([identity])

        await self.repo.update_last_login(
            self.session, identity_id=identity.identity_id, login_at=self.t1
        )
        await self.session.refresh(identity)
        self.assertEqual(identity.last_login_at, self.t1)

    async def test_update_last_login_advances_when_newer(self):
        identity = UserIdentitiesEntity(
            user_id=self.user.user_id,
            subject_identifier="email|newer",
            identity_type="external",
            email_claim="alice@example.com",
            last_login_at=self.t1,
        )
        await self.insert_entities([identity])

        await self.repo.update_last_login(
            self.session, identity_id=identity.identity_id, login_at=self.t2
        )
        await self.session.refresh(identity)
        self.assertEqual(identity.last_login_at, self.t2)

    async def test_update_last_login_no_downgrade_when_older(self):
        identity = UserIdentitiesEntity(
            user_id=self.user.user_id,
            subject_identifier="email|older",
            identity_type="external",
            email_claim="alice@example.com",
            last_login_at=self.t2,
        )
        await self.insert_entities([identity])

        await self.repo.update_last_login(
            self.session, identity_id=identity.identity_id, login_at=self.t1
        )
        await self.session.refresh(identity)
        self.assertEqual(identity.last_login_at, self.t2)

    async def test_get_by_subject_identifier_hit(self):
        identity = UserIdentitiesEntity(
            user_id=self.user.user_id,
            subject_identifier="google-oauth2|sub",
            identity_type="external",
            email_claim="alice@example.com",
        )
        await self.insert_entities([identity])

        found = await self.repo.get_by_subject_identifier(
            self.session, "google-oauth2|sub"
        )
        self.assertIsNotNone(found)
        self.assertEqual(found.identity_id, identity.identity_id)
        self.assertEqual(found.subject_identifier, "google-oauth2|sub")

    async def test_get_by_subject_identifier_not_found(self):
        found = await self.repo.get_by_subject_identifier(self.session, "missing|sub")
        self.assertIsNone(found)

    # list_by_user_id — all identity rows for one user
    async def test_list_by_user_id_returns_all_rows(self):
        internal = UserIdentitiesEntity(
            user_id=self.user.user_id,
            subject_identifier="google-oauth2|internal",
            identity_type="internal",
            email_claim="alice@circlecat.org",
        )
        external = UserIdentitiesEntity(
            user_id=self.user.user_id,
            subject_identifier="email|external",
            identity_type="external",
            email_claim="alice@gmail.com",
        )
        await self.insert_entities([internal, external])

        other = _make_user()
        await self.insert_entities([other])
        await self.insert_entities([
            UserIdentitiesEntity(
                user_id=other.user_id,
                subject_identifier="email|bob",
                identity_type="external",
                email_claim="bob@gmail.com",
            )
        ])

        rows = await self.repo.list_by_user_id(self.session, self.user.user_id)

        self.assertEqual(
            {r.subject_identifier for r in rows},
            {"google-oauth2|internal", "email|external"},
        )

    async def test_list_by_user_id_empty(self):
        rows = await self.repo.list_by_user_id(self.session, self.user.user_id)
        self.assertEqual(rows, [])


if __name__ == "__main__":
    unittest.main()
