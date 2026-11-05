"""Retire email| identity rows, and settle the unconfirmed email claims.

``user_identities`` rows with an ``email|`` subject are obsolete: passwordless
logins resolve by confirmed address (routing) and verify no longer creates
them.

Unconfirmed ``user_emails`` rows come from two sources at migration time:

(a) backup addresses from the retired add-then-verify-later flow, and
(b) primaries seeded unproven -- by b7e3c1d05a92 for every backfilled account
    whose legacy sub was not passwordless (an ``auth0|email|...`` sub was itself
    an OTP round-trip; nothing else was), and at runtime by a first login from a
    non-allowlisted assertion (e.g. google-oauth2 for a u.circlecat.org
    address).

Source (a) is kept. The address is the user's own record of a mailbox they use,
and destroying it silently gives them nothing back. It stays unproven and
non-primary, so it grants no capability until its owner verifies it by adding it
again from the account page; ``user_emails.otp_confirmed`` is what every
capability gate reads, never mere presence.

Source (b) is the account's only email, so leaving it unproven would leave the
account with no confirmed address at all. The backfill placeholders a sub only
when it cannot parse one, so these accounts carry the real sub of the
connection they sign in with, every later login resolves at the sub lookup, and
the swap path that would confirm an address for them never runs -- they would
sit behind the email verification hard wall permanently. Their address is
therefore confirmed outright from ``user_identities.email_claim``: company-held
contact data carried over from the legacy ``users.email``, the same source the
unproven row was written from. Where the row already holds that address it is
promoted in place, which keeps the ``added_at`` the user's own action recorded.

Keeping source (a) is bounded by proof-beats-reservation, which the deletion
used to enforce wholesale: ``user_emails.email`` is globally unique, so an
unproven row would otherwise let one account reserve an address forever against
whoever can actually prove it. An unproven row that stands between another
account and its own claim is released, and at runtime a proven claim takes an
unproven row from its holder.

The needs-link machinery that referenced these rows is deleted in this same
release, and code after this release can no longer create unconfirmed rows at
all (untrusted first logins are refused outright).

The corresponding Auth0 passwordless users stay (inert; nothing routes them
without a claim).

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


# Passwordless logins resolve by confirmed address, and verify no longer writes
# these rows, so an `email|` subject identity carries nothing.
DELETE_EMAIL_IDENTITY_ROWS_SQL = """
    DELETE FROM user_identities WHERE subject_identifier LIKE 'email|%'
"""


# Each account's own claim address: its oldest identity link, the same pick the
# statements below seed and promote from.
_OLDEST_CLAIM_SQL = """
    SELECT DISTINCT ON (i.user_id)
        i.user_id,
        lower(i.email_claim) AS claim
    FROM user_identities i
    WHERE i.email_claim IS NOT NULL
      AND i.email_claim <> ''
    ORDER BY i.user_id, i.linked_at, i.identity_id
"""


# Proof beats reservation. user_emails.email is globally unique, so an unproven
# row held by a different account would silently turn the claimant's seed below
# into a no-op (ON CONFLICT DO NOTHING) and leave them with no confirmed
# address -- held at the verification hard wall by an address nobody ever
# proved. A row that stands in front of another account's own claim is released;
# every other unproven row is kept.
RELEASE_CONTESTED_UNPROVEN_EMAIL_SQL = f"""
    DELETE FROM user_emails e
    USING ({_OLDEST_CLAIM_SQL}) c
    WHERE e.email = c.claim
      AND e.user_id <> c.user_id
      AND e.otp_confirmed = false
"""


# The account already holds its claim address, unproven. Confirm that row rather
# than replacing it, so added_at still says when the user recorded the address.
# Setting both flags at once satisfies user_emails_primary_must_be_confirmed,
# and user_emails_primary_idx cannot be violated: the guard establishes the
# account has no confirmed row, and only a confirmed row may be primary.
PROMOTE_CLAIMED_EMAIL_SQL = f"""
    UPDATE user_emails e
    SET otp_confirmed = true,
        is_primary = true
    FROM ({_OLDEST_CLAIM_SQL}) c
    WHERE e.user_id = c.user_id
      AND e.email = c.claim
      AND NOT EXISTS (
          SELECT 1 FROM user_emails x
          WHERE x.user_id = e.user_id AND x.otp_confirmed
      )
"""


# Seeds a confirmed primary for every account left without one, taking the
# address from its oldest identity claim. Accounts promoted above are already
# excluded by their new confirmed row. ON CONFLICT covers an address another
# account holds *confirmed*: that account proved it, so the claimant is skipped
# rather than aborting the upgrade -- env.py runs every pending migration in a
# single transaction, where one violation would roll back the whole batch.
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
          SELECT 1 FROM user_emails e
          WHERE e.user_id = i.user_id AND e.otp_confirmed
      )
    ORDER BY i.user_id, i.linked_at, i.identity_id
    ON CONFLICT DO NOTHING
"""


# The statements this revision runs, in order.
UPGRADE_SQL = (
    DELETE_EMAIL_IDENTITY_ROWS_SQL,
    RELEASE_CONTESTED_UNPROVEN_EMAIL_SQL,
    PROMOTE_CLAIMED_EMAIL_SQL,
    SEED_CONFIRMED_EMAIL_SQL,
)


def upgrade() -> None:
    """Drop email|-subject identity rows, then give every account a confirmed
    primary -- promoting the row it already holds where there is one."""
    for statement in UPGRADE_SQL:
        op.execute(statement)


def downgrade() -> None:
    """Data-only changes; the deleted rows cannot be restored."""
    pass
