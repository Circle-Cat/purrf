import unittest
from datetime import datetime, timezone

from backend.repository.user_emails_repository import UserEmailsRepository
from backend.entity.users_entity import UsersEntity
from backend.entity.user_emails_entity import UserEmailsEntity
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
        is_active=True,
        updated_timestamp=datetime.now(timezone.utc),
    )


class TestUserEmailsRepository(BaseRepositoryTestLib):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.repo = UserEmailsRepository()

        self.user = _make_user()
        await self.insert_entities([self.user])

    async def test_upsert_email_insert(self):
        email_row = UserEmailsEntity(
            user_id=self.user.user_id,
            email="alice@example.com",
            otp_confirmed=True,
            is_primary=True,
        )
        merged = await self.repo.upsert_email(self.session, email_row)

        self.assertIsNotNone(merged.email_id)
        self.assertEqual(merged.email, "alice@example.com")
        self.assertTrue(merged.otp_confirmed)
        self.assertTrue(merged.is_primary)

    async def test_upsert_email_insert_unconfirmed_non_primary(self):
        email_row = UserEmailsEntity(
            user_id=self.user.user_id,
            email="extra@example.com",
            otp_confirmed=False,
            is_primary=False,
        )
        merged = await self.repo.upsert_email(self.session, email_row)

        self.assertIsNotNone(merged.email_id)
        self.assertFalse(merged.otp_confirmed)
        self.assertFalse(merged.is_primary)

    async def test_upsert_email_update(self):
        email_row = UserEmailsEntity(
            user_id=self.user.user_id,
            email="alice@example.com",
            otp_confirmed=False,
            is_primary=False,
        )
        await self.insert_entities([email_row])

        email_row.otp_confirmed = True
        merged = await self.repo.upsert_email(self.session, email_row)

        self.assertEqual(merged.email_id, email_row.email_id)
        self.assertTrue(merged.otp_confirmed)

    async def test_list_by_user_id_returns_all_rows(self):
        primary = UserEmailsEntity(
            user_id=self.user.user_id,
            email="alice@example.com",
            otp_confirmed=True,
            is_primary=True,
        )
        pending = UserEmailsEntity(
            user_id=self.user.user_id,
            email="pending@example.com",
            otp_confirmed=False,
            is_primary=False,
        )
        await self.insert_entities([primary, pending])

        other = _make_user()
        await self.insert_entities([other])
        await self.insert_entities([
            UserEmailsEntity(
                user_id=other.user_id,
                email="bob@example.com",
                otp_confirmed=True,
                is_primary=True,
            )
        ])

        rows = await self.repo.list_by_user_id(self.session, self.user.user_id)

        self.assertEqual(
            {r.email for r in rows}, {"alice@example.com", "pending@example.com"}
        )

    async def test_list_by_user_id_empty(self):
        rows = await self.repo.list_by_user_id(self.session, self.user.user_id)
        self.assertEqual(rows, [])

    async def test_get_by_id_returns_row(self):
        email_row = UserEmailsEntity(
            user_id=self.user.user_id,
            email="alice@example.com",
            otp_confirmed=True,
            is_primary=True,
        )
        await self.insert_entities([email_row])

        fetched = await self.repo.get_by_id(self.session, email_row.email_id)

        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.email_id, email_row.email_id)
        self.assertEqual(fetched.email, "alice@example.com")

    async def test_get_confirmed_by_email_returns_confirmed_row(self):
        row = UserEmailsEntity(
            user_id=self.user.user_id,
            email="owned@example.com",
            otp_confirmed=True,
            is_primary=True,
        )
        await self.repo.upsert_email(self.session, row)

        found = await self.repo.get_confirmed_by_email(
            self.session, "owned@example.com"
        )

        self.assertIsNotNone(found)
        self.assertEqual(found.user_id, self.user.user_id)
        self.assertTrue(found.otp_confirmed)

    async def test_get_confirmed_by_email_ignores_unconfirmed(self):
        row = UserEmailsEntity(
            user_id=self.user.user_id,
            email="unconfirmed@example.com",
            otp_confirmed=False,
            is_primary=False,
        )
        await self.repo.upsert_email(self.session, row)

        found = await self.repo.get_confirmed_by_email(
            self.session, "unconfirmed@example.com"
        )

        self.assertIsNone(found)

    async def test_get_confirmed_by_email_unknown_returns_none(self):
        found = await self.repo.get_confirmed_by_email(
            self.session, "nobody@example.com"
        )
        self.assertIsNone(found)

    async def test_exists_on_other_user_counts_unconfirmed_claim(self):
        # user_emails.email is globally unique, so even an unverified claim on
        # another account makes the address unavailable.
        other = _make_user()
        await self.insert_entities([other])
        await self.insert_entities([
            UserEmailsEntity(
                user_id=other.user_id,
                email="taken@example.com",
                otp_confirmed=False,
                is_primary=False,
            )
        ])

        self.assertTrue(
            await self.repo.exists_on_other_user(
                self.session, "taken@example.com", self.user.user_id
            )
        )

    async def test_exists_on_other_user_ignores_own_claim(self):
        await self.insert_entities([
            UserEmailsEntity(
                user_id=self.user.user_id,
                email="mine@example.com",
                otp_confirmed=True,
                is_primary=True,
            )
        ])

        self.assertFalse(
            await self.repo.exists_on_other_user(
                self.session, "mine@example.com", self.user.user_id
            )
        )

    async def test_exists_on_other_user_unknown_returns_false(self):
        self.assertFalse(
            await self.repo.exists_on_other_user(
                self.session, "nobody@example.com", self.user.user_id
            )
        )

    async def test_get_by_id_missing_returns_none(self):
        fetched = await self.repo.get_by_id(self.session, 99999999)
        self.assertIsNone(fetched)

    async def test_set_primary_swaps_primary_flag(self):
        old_primary = UserEmailsEntity(
            user_id=self.user.user_id,
            email="alice@example.com",
            otp_confirmed=True,
            is_primary=True,
        )
        target = UserEmailsEntity(
            user_id=self.user.user_id,
            email="alice.work@example.com",
            otp_confirmed=True,
            is_primary=False,
        )
        await self.insert_entities([old_primary, target])

        await self.repo.set_primary(self.session, self.user.user_id, target.email_id)

        rows = await self.repo.list_by_user_id(self.session, self.user.user_id)
        by_email = {r.email: r for r in rows}
        self.assertFalse(by_email["alice@example.com"].is_primary)
        self.assertTrue(by_email["alice.work@example.com"].is_primary)

    async def test_delete_removes_row(self):
        email_row = UserEmailsEntity(
            user_id=self.user.user_id,
            email="alice@example.com",
            otp_confirmed=True,
            is_primary=False,
        )
        await self.insert_entities([email_row])

        await self.repo.delete(self.session, email_row.email_id)

        self.assertIsNone(await self.repo.get_by_id(self.session, email_row.email_id))

    async def test_delete_leaves_other_rows_intact(self):
        target = UserEmailsEntity(
            user_id=self.user.user_id,
            email="alice@example.com",
            otp_confirmed=True,
            is_primary=False,
        )
        keep = UserEmailsEntity(
            user_id=self.user.user_id,
            email="alice.work@example.com",
            otp_confirmed=True,
            is_primary=True,
        )
        await self.insert_entities([target, keep])

        await self.repo.delete(self.session, target.email_id)

        rows = await self.repo.list_by_user_id(self.session, self.user.user_id)
        self.assertEqual({r.email for r in rows}, {"alice.work@example.com"})

    async def test_delete_missing_id_is_noop(self):
        # Deleting a row that does not exist should not raise.
        await self.repo.delete(self.session, 99999999)

    # get_emails_by_user_ids — backs Meet attendance any-address matching
    async def test_get_emails_by_user_ids_returns_all_rows(self):
        other = _make_user()
        await self.insert_entities([other])
        await self.insert_entities([
            UserEmailsEntity(
                user_id=self.user.user_id,
                email="primary@example.com",
                otp_confirmed=True,
                is_primary=True,
            ),
            UserEmailsEntity(
                user_id=self.user.user_id,
                email="alt1@example.com",
                otp_confirmed=False,
                is_primary=False,
            ),
            UserEmailsEntity(
                user_id=other.user_id,
                email="otheralt@example.com",
                otp_confirmed=False,
                is_primary=False,
            ),
        ])

        result = await self.repo.get_emails_by_user_ids(
            self.session, [self.user.user_id, other.user_id]
        )

        self.assertEqual(
            {
                self.user.user_id: sorted(result[self.user.user_id]),
                other.user_id: result[other.user_id],
            },
            {
                self.user.user_id: ["alt1@example.com", "primary@example.com"],
                other.user_id: ["otheralt@example.com"],
            },
        )

    async def test_get_emails_by_user_ids_empty_input(self):
        result = await self.repo.get_emails_by_user_ids(self.session, [])
        self.assertEqual(result, {})

    # get_contact_emails_by_user_ids — the user_emails replacement for reading
    # legacy users.primary_email as a contact/display address
    async def test_get_contact_emails_by_user_ids_prefers_primary(self):
        await self.insert_entities([
            UserEmailsEntity(
                user_id=self.user.user_id,
                email="older@example.com",
                otp_confirmed=False,
                is_primary=False,
            ),
            UserEmailsEntity(
                user_id=self.user.user_id,
                email="primary@example.com",
                otp_confirmed=True,
                is_primary=True,
            ),
        ])

        result = await self.repo.get_contact_emails_by_user_ids(
            self.session, [self.user.user_id]
        )

        self.assertEqual(result, {self.user.user_id: "primary@example.com"})

    async def test_get_contact_emails_by_user_ids_falls_back_to_oldest_claim(self):
        # No primary yet (e.g. a user still in front of the verify wall): the
        # oldest claim — the address seeded from the login — stands in, which
        # matches what the legacy users.primary_email column held.
        await self.insert_entities([
            UserEmailsEntity(
                user_id=self.user.user_id,
                email="seeded@example.com",
                otp_confirmed=False,
                is_primary=False,
            )
        ])
        await self.insert_entities([
            UserEmailsEntity(
                user_id=self.user.user_id,
                email="added-later@example.com",
                otp_confirmed=False,
                is_primary=False,
            )
        ])

        result = await self.repo.get_contact_emails_by_user_ids(
            self.session, [self.user.user_id]
        )

        self.assertEqual(result, {self.user.user_id: "seeded@example.com"})

    async def test_get_contact_emails_by_user_ids_omits_user_without_rows(self):
        result = await self.repo.get_contact_emails_by_user_ids(
            self.session, [self.user.user_id]
        )
        self.assertEqual(result, {})

    async def test_get_contact_emails_by_user_ids_empty_input(self):
        result = await self.repo.get_contact_emails_by_user_ids(self.session, [])
        self.assertEqual(result, {})

    async def test_get_contact_email_single_user(self):
        await self.insert_entities([
            UserEmailsEntity(
                user_id=self.user.user_id,
                email="primary@example.com",
                otp_confirmed=True,
                is_primary=True,
            )
        ])

        self.assertEqual(
            await self.repo.get_contact_email(self.session, self.user.user_id),
            "primary@example.com",
        )

    async def test_get_contact_email_missing_returns_none(self):
        self.assertIsNone(
            await self.repo.get_contact_email(self.session, self.user.user_id)
        )


if __name__ == "__main__":
    unittest.main()
