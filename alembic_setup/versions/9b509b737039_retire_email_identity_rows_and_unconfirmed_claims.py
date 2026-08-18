"""Retire email| identity rows and unconfirmed email claims.

user_identities rows with an 'email|' subject are obsolete: passwordless
logins resolve by confirmed address (routing) and verify no longer creates
them. Unconfirmed user_emails rows come from two sources at migration time:
(a) backup addresses from the retired add-then-verify-later flow, and
(b) primaries seeded unproven — by b7e3c1d05a92 for every backfilled account
whose legacy sub was not passwordless (an 'auth0|email|...' sub was itself an
OTP round-trip; nothing else was), and at runtime by a first login from a
non-allowlisted assertion (e.g. google-oauth2 for a u.circlecat.org address).
Both are deleted by owner decision: the rows were never proof of anything,
and releasing an address from an unproven reservation to whoever can actually
prove it is the intended proof-beats-reservation semantics. Accounts survive
untouched, and a deleted backup address costs its owner nothing — they keep
their confirmed primary.

Source (b) is different: that row is the account's only email, so the
deletion leaves it with none at all. The backfill placeholders a sub only
when it cannot parse one, so these accounts carry the real sub of the
connection they sign in with, every later login resolves at the sub lookup,
and the swap path that would confirm an address for them never runs — they
would sit behind the "Set your contact email" hard wall permanently. Their
address is therefore re-seeded as a confirmed primary from
user_identities.email_claim: company-held contact data carried over from the
legacy users.email, the same source the deleted row was written from.

The needs-link machinery that referenced these rows is deleted in this same
release, and code after this release can no longer create unconfirmed rows at
all (untrusted first logins are refused outright). The corresponding Auth0
passwordless users stay (inert; nothing routes them without a claim).

Revision ID: 9b509b737039
Revises: b8d2f5a91c37
Create Date: 2026-07-18 12:30:00.000000
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "9b509b737039"
down_revision: Union[str, Sequence[str], None] = "b8d2f5a91c37"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Seeds a confirmed primary for every account the deletion above leaves with no
# email row at all, taking the address from the account's oldest identity claim.
# ON CONFLICT covers an address another account already holds (user_emails.email
# is globally unique): that account proved it, so the claimant is skipped rather
# than aborting the upgrade -- env.py runs every pending migration in a single
# transaction, where one violation would roll back the whole batch.
SEED_CONFIRMED_EMAIL_SQL = """
    INSERT INTO user_emails (user_id, email, otp_confirmed, is_primary)
    SELECT DISTINCT ON (i.user_id)
        i.user_id,
        lower(i.email_claim),
        true,
        true
    FROM user_identities i
    WHERE i.email_claim IS NOT NULL
      AND i.email_claim <> ''
      AND NOT EXISTS (
          SELECT 1 FROM user_emails e WHERE e.user_id = i.user_id
      )
    ORDER BY i.user_id, i.linked_at, i.identity_id
    ON CONFLICT DO NOTHING
"""


def upgrade() -> None:
    """Delete email|-subject identity rows and unconfirmed email claims, then
    re-seed a confirmed primary for any account left without one."""
    op.execute("DELETE FROM user_identities WHERE subject_identifier LIKE 'email|%'")
    op.execute("DELETE FROM user_emails WHERE otp_confirmed = false")
    op.execute(SEED_CONFIRMED_EMAIL_SQL)


def downgrade() -> None:
    """Data-only deletion; the removed rows cannot be restored."""
    pass
