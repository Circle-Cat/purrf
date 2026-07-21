import unittest
from datetime import datetime, timezone

from backend.repository.user_identities_repository import UserIdentitiesRepository
from backend.entity.users_entity import UsersEntity
from backend.entity.user_identities_entity import UserIdentitiesEntity
from backend.common.mentorship_enums import CommunicationMethod
from tests.backend_test.repository_test.base_repository_test_lib import (
    BaseRepositoryTestLib,
)


def _make_user(is_active: bool = True) -> UsersEntity:
    return UsersEntity(
        first_name="Alice",
        last_name="Admin",
        timezone="Asia/Shanghai",
        timezone_updated_at=datetime.now(timezone.utc),
        communication_channel=CommunicationMethod.EMAIL,
        is_active=is_active,
        updated_timestamp=datetime.now(timezone.utc),
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

    # exists_active_internal — active employee = is_active AND an INTERNAL identity
    async def test_exists_active_internal_true_for_active_internal(self):
        await self.insert_entities([
            UserIdentitiesEntity(
                user_id=self.user.user_id,
                subject_identifier="google-oauth2|internal",
                identity_type="internal",
                email_claim="alice@circlecat.org",
            )
        ])

        result = await self.repo.exists_active_internal(self.session, self.user.user_id)
        self.assertTrue(result)

    async def test_exists_active_internal_false_without_internal_identity(self):
        await self.insert_entities([
            UserIdentitiesEntity(
                user_id=self.user.user_id,
                subject_identifier="email|external",
                identity_type="external",
                email_claim="alice@gmail.com",
            )
        ])

        result = await self.repo.exists_active_internal(self.session, self.user.user_id)
        self.assertFalse(result)

    async def test_exists_active_internal_false_when_inactive(self):
        inactive = _make_user(is_active=False)
        await self.insert_entities([inactive])
        await self.insert_entities([
            UserIdentitiesEntity(
                user_id=inactive.user_id,
                subject_identifier="google-oauth2|inactive",
                identity_type="internal",
                email_claim="ex@circlecat.org",
            )
        ])

        result = await self.repo.exists_active_internal(self.session, inactive.user_id)
        self.assertFalse(result)

    async def test_exists_active_internal_false_for_unknown_user(self):
        result = await self.repo.exists_active_internal(self.session, 9999999)
        self.assertFalse(result)

    async def test_exists_active_internal_ignores_other_users_internal(self):
        """Another user's INTERNAL identity must not make this user qualify."""
        other = _make_user()
        await self.insert_entities([other])
        await self.insert_entities([
            UserIdentitiesEntity(
                user_id=other.user_id,
                subject_identifier="google-oauth2|other-internal",
                identity_type="internal",
                email_claim="bob@circlecat.org",
            )
        ])

        result = await self.repo.exists_active_internal(self.session, self.user.user_id)
        self.assertFalse(result)

    # get_by_id / delete — back the unlink flow
    async def test_get_by_id_returns_row(self):
        identity = UserIdentitiesEntity(
            user_id=self.user.user_id,
            subject_identifier="email|byid",
            identity_type="external",
            email_claim="alice@gmail.com",
        )
        await self.insert_entities([identity])

        found = await self.repo.get_by_id(self.session, identity.identity_id)
        self.assertIsNotNone(found)
        self.assertEqual(found.subject_identifier, "email|byid")

    async def test_get_by_id_none_when_absent(self):
        found = await self.repo.get_by_id(self.session, 9999999)
        self.assertIsNone(found)

    async def test_delete_removes_only_target_row(self):
        keep = UserIdentitiesEntity(
            user_id=self.user.user_id,
            subject_identifier="google-oauth2|keep",
            identity_type="internal",
            email_claim="alice@circlecat.org",
        )
        drop = UserIdentitiesEntity(
            user_id=self.user.user_id,
            subject_identifier="email|drop",
            identity_type="external",
            email_claim="alice@gmail.com",
        )
        await self.insert_entities([keep, drop])

        await self.repo.delete(self.session, drop.identity_id)

        self.assertIsNone(await self.repo.get_by_id(self.session, drop.identity_id))
        remaining = await self.repo.list_by_user_id(self.session, self.user.user_id)
        self.assertEqual(
            {r.subject_identifier for r in remaining}, {"google-oauth2|keep"}
        )

    # get_google_subs_by_user_ids — backs Meet attendance's local UID->email cache
    async def test_get_google_subs_by_user_ids_returns_only_google(self):
        other_user = _make_user()
        await self.insert_entities([other_user])
        google = UserIdentitiesEntity(
            user_id=self.user.user_id,
            subject_identifier="google-oauth2|12345",
            identity_type="external",
            email_claim="alice@example.com",
        )
        email = UserIdentitiesEntity(
            user_id=self.user.user_id,
            subject_identifier="email|abc",
            identity_type="external",
            email_claim="alice@example.com",
        )
        other_google = UserIdentitiesEntity(
            user_id=other_user.user_id,
            subject_identifier="google-oauth2|99999",
            identity_type="external",
            email_claim="bob@example.com",
        )
        await self.insert_entities([google, email, other_google])

        result = await self.repo.get_google_subs_by_user_ids(
            self.session, [self.user.user_id, other_user.user_id]
        )

        self.assertEqual(
            result,
            {
                self.user.user_id: ["google-oauth2|12345"],
                other_user.user_id: ["google-oauth2|99999"],
            },
        )

    async def test_get_google_subs_by_user_ids_returns_all_google_for_user(self):
        google_one = UserIdentitiesEntity(
            user_id=self.user.user_id,
            subject_identifier="google-oauth2|first",
            identity_type="external",
            email_claim="alice@example.com",
        )
        google_two = UserIdentitiesEntity(
            user_id=self.user.user_id,
            subject_identifier="google-oauth2|second",
            identity_type="external",
            email_claim="alice@work.com",
        )
        await self.insert_entities([google_one, google_two])

        result = await self.repo.get_google_subs_by_user_ids(
            self.session, [self.user.user_id]
        )

        self.assertEqual(
            {self.user.user_id: sorted(result[self.user.user_id])},
            {self.user.user_id: ["google-oauth2|first", "google-oauth2|second"]},
        )

    async def test_get_google_subs_by_user_ids_empty_input(self):
        result = await self.repo.get_google_subs_by_user_ids(self.session, [])
        self.assertEqual(result, {})

    async def test_get_google_subs_by_user_ids_no_google_identity(self):
        email = UserIdentitiesEntity(
            user_id=self.user.user_id,
            subject_identifier="email|onlyemail",
            identity_type="external",
            email_claim="alice@example.com",
        )
        await self.insert_entities([email])

        result = await self.repo.get_google_subs_by_user_ids(
            self.session, [self.user.user_id]
        )

        self.assertEqual(result, {})


if __name__ == "__main__":
    unittest.main()
