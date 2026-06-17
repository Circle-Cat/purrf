import unittest
import uuid
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
        primary_email=f"{uuid.uuid4()}@example.com",
        is_active=True,
        updated_timestamp=datetime.now(timezone.utc),
        subject_identifier=str(uuid.uuid4()),
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


if __name__ == "__main__":
    unittest.main()
