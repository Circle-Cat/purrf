import re
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select, text

from backend.common.mentorship_enums import CommunicationMethod
from backend.entity.user_emails_entity import UserEmailsEntity
from backend.entity.user_identities_entity import UserIdentitiesEntity
from backend.entity.users_entity import UsersEntity
from tests.backend_test.repository_test.base_repository_test_lib import (
    BaseRepositoryTestLib,
)

_MIGRATION_PATH = Path(
    "alembic_setup/versions/"
    "9b509b737039_retire_email_identity_rows_and_unconfirmed_claims.py"
)


def _seed_sql() -> str:
    """The migration's seeding statement, read out of the migration itself.

    Reading the constant rather than restating it here means the SQL these
    tests exercise is byte-for-byte the SQL that ships.
    """
    source = _MIGRATION_PATH.read_text(encoding="utf-8")
    match = re.search(r'SEED_CONFIRMED_EMAIL_SQL = """(.*?)"""', source, re.DOTALL)
    if match is None:
        raise AssertionError(f"SEED_CONFIRMED_EMAIL_SQL not found in {_MIGRATION_PATH}")
    return match.group(1)


def _seed_sql_statement():
    """The migration's seeding statement, ready to execute."""
    return text(_seed_sql())


def _make_user() -> UsersEntity:
    """Build a UsersEntity satisfying every NOT NULL column."""
    return UsersEntity(
        first_name="A",
        last_name="B",
        timezone="UTC",
        timezone_updated_at=datetime.now(timezone.utc),
        communication_channel=CommunicationMethod.EMAIL,
        is_active=True,
        updated_timestamp=datetime.now(timezone.utc),
    )


class RetireUnconfirmedEmailsMigrationTest(BaseRepositoryTestLib):
    """Verifies the seeding step of migration 9b509b737039.

    Deleting every unconfirmed row leaves the accounts that were backfilled
    from a legacy social sub with no contact email at all -- their identity
    row was written with the real sub, so no later login ever runs the swap
    path that would confirm one, and they would be held at the hard wall
    forever. The migration therefore re-seeds a confirmed primary from the
    identity's email_claim, which is the address the legacy system already
    held for them.
    """

    async def _emails_of(self, user_id: int) -> list[UserEmailsEntity]:
        result = await self.session.execute(
            select(UserEmailsEntity)
            .where(UserEmailsEntity.user_id == user_id)
            .order_by(UserEmailsEntity.email_id)
        )
        return list(result.scalars().all())

    async def test_seeds_confirmed_primary_from_identity_claim(self):
        user = _make_user()
        await self.insert_entities([user])
        await self.insert_entities([
            UserIdentitiesEntity(
                user_id=user.user_id,
                subject_identifier=f"google-oauth2|seed-{user.user_id}",
                email_claim="googler@circlecat.org",
            )
        ])

        await self.session.execute(_seed_sql_statement())

        rows = await self._emails_of(user.user_id)
        self.assertEqual(1, len(rows))
        self.assertEqual("googler@circlecat.org", rows[0].email)
        self.assertTrue(rows[0].otp_confirmed)
        self.assertTrue(rows[0].is_primary)

    async def test_claim_is_lowercased(self):
        user = _make_user()
        await self.insert_entities([user])
        await self.insert_entities([
            UserIdentitiesEntity(
                user_id=user.user_id,
                subject_identifier=f"google-oauth2|mixed-{user.user_id}",
                email_claim="MiXeD@circlecat.org",
            )
        ])

        await self.session.execute(_seed_sql_statement())

        rows = await self._emails_of(user.user_id)
        self.assertEqual(["mixed@circlecat.org"], [row.email for row in rows])

    async def test_account_that_still_has_an_email_is_untouched(self):
        user = _make_user()
        await self.insert_entities([user])
        await self.insert_entities([
            UserEmailsEntity(
                user_id=user.user_id,
                email="kept@circlecat.org",
                otp_confirmed=True,
                is_primary=True,
            ),
            UserIdentitiesEntity(
                user_id=user.user_id,
                subject_identifier=f"google-oauth2|kept-{user.user_id}",
                email_claim="stale-claim@circlecat.org",
            ),
        ])

        await self.session.execute(_seed_sql_statement())

        rows = await self._emails_of(user.user_id)
        self.assertEqual(["kept@circlecat.org"], [row.email for row in rows])

    async def test_account_whose_only_email_is_not_primary_is_untouched(self):
        # Having any email row at all disqualifies an account, primary or not:
        # the one-primary-per-account partial index would mask a stray insert
        # for anyone who already has a primary, so this is what actually pins
        # the "no email row at all" condition.
        user = _make_user()
        await self.insert_entities([user])
        await self.insert_entities([
            UserEmailsEntity(
                user_id=user.user_id,
                email="secondary@circlecat.org",
                otp_confirmed=True,
                is_primary=False,
            ),
            UserIdentitiesEntity(
                user_id=user.user_id,
                subject_identifier=f"google-oauth2|secondary-{user.user_id}",
                email_claim="stale-claim-2@circlecat.org",
            ),
        ])

        await self.session.execute(_seed_sql_statement())

        rows = await self._emails_of(user.user_id)
        self.assertEqual(["secondary@circlecat.org"], [row.email for row in rows])

    async def test_claim_owned_by_another_account_is_skipped(self):
        owner = _make_user()
        claimant = _make_user()
        await self.insert_entities([owner, claimant])
        await self.insert_entities([
            UserEmailsEntity(
                user_id=owner.user_id,
                email="contested@circlecat.org",
                otp_confirmed=True,
                is_primary=True,
            ),
            UserIdentitiesEntity(
                user_id=claimant.user_id,
                subject_identifier=f"google-oauth2|contested-{claimant.user_id}",
                email_claim="contested@circlecat.org",
            ),
        ])

        # An address belongs to at most one account, so the loser is skipped
        # rather than raising -- env.py runs the whole upgrade in one
        # transaction, where a single violation would roll back every
        # migration in the batch.
        await self.session.execute(_seed_sql_statement())

        self.assertEqual([], await self._emails_of(claimant.user_id))
        self.assertEqual(1, len(await self._emails_of(owner.user_id)))

    async def test_multiple_identities_seed_a_single_row(self):
        user = _make_user()
        await self.insert_entities([user])
        earlier = datetime.now(timezone.utc) - timedelta(days=2)
        await self.insert_entities([
            UserIdentitiesEntity(
                user_id=user.user_id,
                subject_identifier=f"google-oauth2|first-{user.user_id}",
                email_claim="first@circlecat.org",
                linked_at=earlier,
            ),
            UserIdentitiesEntity(
                user_id=user.user_id,
                subject_identifier=f"google-oauth2|second-{user.user_id}",
                email_claim="second@circlecat.org",
                linked_at=datetime.now(timezone.utc),
            ),
        ])

        await self.session.execute(_seed_sql_statement())

        # One primary per account is a partial unique index; the oldest link
        # wins so the seeded address is deterministic.
        rows = await self._emails_of(user.user_id)
        self.assertEqual(["first@circlecat.org"], [row.email for row in rows])

    async def test_identity_without_a_claim_is_skipped(self):
        user = _make_user()
        await self.insert_entities([user])
        await self.insert_entities([
            UserIdentitiesEntity(
                user_id=user.user_id,
                subject_identifier=f"google-oauth2|claimless-{user.user_id}",
                email_claim=None,
            )
        ])

        await self.session.execute(_seed_sql_statement())

        self.assertEqual([], await self._emails_of(user.user_id))


if __name__ == "__main__":
    unittest.main()
