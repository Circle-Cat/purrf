"""Bulk address lookup, used to map Azure ldaps onto purrf accounts."""

import datetime

from backend.common.mentorship_enums import CommunicationMethod
from backend.entity.user_emails_entity import UserEmailsEntity
from backend.entity.users_entity import UsersEntity
from backend.repository.user_emails_repository import UserEmailsRepository
from tests.backend_test.repository_test.base_repository_test_lib import (
    BaseRepositoryTestLib,
)


def _make_user() -> UsersEntity:
    return UsersEntity(
        first_name="U",
        last_name="Ser",
        timezone="Asia/Shanghai",
        timezone_updated_at=datetime.datetime.now(datetime.timezone.utc),
        communication_channel=CommunicationMethod.EMAIL,
        is_active=True,
        updated_timestamp=datetime.datetime.now(datetime.timezone.utc),
    )


class TestListByEmails(BaseRepositoryTestLib):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.repository = UserEmailsRepository()
        self.first = _make_user()
        self.second = _make_user()
        await self.insert_entities([self.first, self.second])

    async def test_every_address_asked_for_that_exists_comes_back(self):
        """One query for a whole directory, rather than two per person: the
        accrual job has to try both internal domains for every employee."""
        await self.insert_entities([
            UserEmailsEntity(user_id=self.first.user_id, email="ann@circlecat.org"),
            UserEmailsEntity(user_id=self.second.user_id, email="bob@u.circlecat.org"),
            UserEmailsEntity(user_id=self.second.user_id, email="bob@personal.com"),
        ])

        rows = await self.repository.list_by_emails(
            self.session,
            ["ann@circlecat.org", "bob@u.circlecat.org", "nobody@circlecat.org"],
        )

        self.assertEqual(
            {row.email: row.user_id for row in rows},
            {
                "ann@circlecat.org": self.first.user_id,
                "bob@u.circlecat.org": self.second.user_id,
            },
        )

    async def test_an_unconfirmed_address_still_comes_back(self):
        """Whether an address is proven is the caller's business. A corporate
        address arriving through SSO may carry no OTP, and dropping it here
        would silently exclude that person from accrual."""
        await self.insert_entities([
            UserEmailsEntity(
                user_id=self.first.user_id,
                email="ann@circlecat.org",
                otp_confirmed=False,
            )
        ])

        rows = await self.repository.list_by_emails(self.session, ["ann@circlecat.org"])

        self.assertEqual(len(rows), 1)

    async def test_asking_for_nothing_queries_nothing(self):
        self.assertEqual(await self.repository.list_by_emails(self.session, []), [])


if __name__ == "__main__":
    import unittest

    unittest.main()
