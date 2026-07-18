"""add last_login_at to users

Revision ID: e1c8a3d4f6b2
Revises: a7c4e9f21b56
Create Date: 2026-07-18 00:00:00.000000

Account-level last-login timestamp, stamped by the auth middleware on every
successful human sign-in path. Passwordless logins now route by confirmed
email rather than a user_identities row, so per-identity last_login_at alone
would go stale; this column stays complete regardless of which path resolved
the user.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e1c8a3d4f6b2"
down_revision: Union[str, Sequence[str], None] = "a7c4e9f21b56"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "users", sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("users", "last_login_at")
