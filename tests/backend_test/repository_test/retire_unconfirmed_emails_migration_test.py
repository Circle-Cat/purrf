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


def _sql(name: str) -> str:
    """One named SQL constant, read out of the migration itself.

    Reading the constant rather than restating it here means the SQL these
    tests exercise is byte-for-byte the SQL that ships. `{_NAME}` placeholders
    are resolved from the migration's own constants, the same substitution its
    f-strings perform at import.
    """
    source = _MIGRATION_PATH.read_text(encoding="utf-8")
    match = re.search(name + r' = f?"""(.*?)"""', source, re.DOTALL)
    if match is None:
        raise AssertionError(f"{name} not found in {_MIGRATION_PATH}")
    statement = match.group(1)
    for placeholder in set(re.findall(r"\{([A-Za-z_]+)\}", statement)):
        statement = statement.replace("{" + placeholder + "}", _sql(placeholder))
    return statement


def _seed_sql_statement():
    """The migration's seeding statement, ready to execute."""
    return text(_sql("SEED_CONFIRMED_EMAIL_SQL"))


def _upgrade_statements() -> list:
    """Every statement upgrade() runs, in the order UPGRADE_SQL lists them.

    Taking both the names and their order from the migration means a statement
    added, removed or reordered there changes what these tests run.
    """
    source = _MIGRATION_PATH.read_text(encoding="utf-8")
    match = re.search(r"UPGRADE_SQL = \((.*?)\)", source, re.DOTALL)
    if match is None:
        raise AssertionError(f"UPGRADE_SQL not found in {_MIGRATION_PATH}")
    names = re.findall(r"([A-Z_]+)\s*,?", match.group(1))
    if not names:
        raise AssertionError(f"UPGRADE_SQL in {_MIGRATION_PATH} lists no statements")
    return [text(_sql(name)) for name in names]


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

    async def _run_upgrade(self) -> None:
        """Run every statement upgrade() runs, in order."""
        for statement in _upgrade_statements():
            await self.session.execute(statement)

    async def test_unconfirmed_alternative_survives_and_claim_is_still_seeded(self):
        # A backup address added under the retired add-then-verify-later flow
        # is the user's own record of a mailbox they use. It stays, unproven,
        # and the account still gets its claim address as a confirmed primary.
        user = _make_user()
        await self.insert_entities([user])
        await self.insert_entities([
            UserEmailsEntity(
                user_id=user.user_id,
                email="legacy-backup@example.com",
                otp_confirmed=False,
                is_primary=False,
            ),
            UserIdentitiesEntity(
                user_id=user.user_id,
                subject_identifier=f"google-oauth2|keeps-{user.user_id}",
                email_claim="claim@circlecat.org",
            ),
        ])

        await self._run_upgrade()

        rows = await self._emails_of(user.user_id)
        by_email = {row.email: row for row in rows}
        self.assertEqual(
            {"legacy-backup@example.com", "claim@circlecat.org"}, set(by_email)
        )
        backup = by_email["legacy-backup@example.com"]
        self.assertFalse(backup.otp_confirmed)
        self.assertFalse(backup.is_primary)
        claim = by_email["claim@circlecat.org"]
        self.assertTrue(claim.otp_confirmed)
        self.assertTrue(claim.is_primary)

    async def test_claim_already_present_unproven_is_promoted_in_place(self):
        # Promoting the existing row rather than deleting and re-inserting it
        # keeps added_at, the date the user actually recorded the address.
        user = _make_user()
        await self.insert_entities([user])
        recorded_at = datetime.now(timezone.utc) - timedelta(days=400)
        await self.insert_entities([
            UserEmailsEntity(
                user_id=user.user_id,
                email="claim@circlecat.org",
                otp_confirmed=False,
                is_primary=False,
                added_at=recorded_at,
            ),
            UserIdentitiesEntity(
                user_id=user.user_id,
                subject_identifier=f"google-oauth2|promote-{user.user_id}",
                email_claim="claim@circlecat.org",
            ),
        ])

        await self._run_upgrade()

        rows = await self._emails_of(user.user_id)
        self.assertEqual(1, len(rows))
        self.assertTrue(rows[0].otp_confirmed)
        self.assertTrue(rows[0].is_primary)
        self.assertEqual(recorded_at, rows[0].added_at)

    async def test_unproven_row_on_another_account_is_released_to_the_claimant(self):
        # user_emails.email is globally unique, so an unproven row held by a
        # different account would make the claimant's seed a no-op and leave
        # them with no confirmed email -- back behind the hard wall. Proof
        # beats reservation: the unproven row goes.
        squatter = _make_user()
        claimant = _make_user()
        await self.insert_entities([squatter, claimant])
        await self.insert_entities([
            UserEmailsEntity(
                user_id=squatter.user_id,
                email="contested@circlecat.org",
                otp_confirmed=False,
                is_primary=False,
            ),
            UserIdentitiesEntity(
                user_id=claimant.user_id,
                subject_identifier=f"google-oauth2|claims-{claimant.user_id}",
                email_claim="contested@circlecat.org",
            ),
        ])

        await self._run_upgrade()

        self.assertEqual([], await self._emails_of(squatter.user_id))
        rows = await self._emails_of(claimant.user_id)
        self.assertEqual(["contested@circlecat.org"], [row.email for row in rows])
        self.assertTrue(rows[0].otp_confirmed)


if __name__ == "__main__":
    unittest.main()
