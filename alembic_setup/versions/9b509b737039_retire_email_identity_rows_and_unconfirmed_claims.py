"""Retire email| identity rows and unconfirmed email claims.

user_identities rows with an 'email|' subject are obsolete: passwordless
logins resolve by confirmed address (routing) and verify no longer creates
them. Unconfirmed user_emails rows come from two sources at migration time:
(a) backup addresses from the retired add-then-verify-later flow, and
(b) first-login seeds from non-allowlisted assertions (e.g., google-oauth2
for u.circlecat.org addresses) whose owners have not yet passed the verify
wall. Both are deleted by owner decision. This deletion is acceptable because
the rows were never proof of anything — accounts survive untouched, an
affected user's next login lands on the repurposed "Set your contact email"
wall, and one OTP re-establishes a confirmed primary; releasing an address
from an unproven reservation to whoever can actually prove it is the intended
proof-beats-reservation semantics. The needs-link machinery that referenced
these rows is deleted in this same release, and code after this release can
no longer create unconfirmed rows at all (untrusted first logins are refused
outright). The corresponding Auth0 passwordless users stay (inert; nothing
routes them without a claim).

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


def upgrade() -> None:
    """Delete email|-subject identity rows and unconfirmed email claims."""
    op.execute("DELETE FROM user_identities WHERE subject_identifier LIKE 'email|%'")
    op.execute("DELETE FROM user_emails WHERE otp_confirmed = false")


def downgrade() -> None:
    """Data-only deletion; the removed rows cannot be restored."""
    pass
