"""add withdrawn and inactive enum values

Revision ID: 63158db8a00a
Revises: 9b3d1ba0df5e
Create Date: 2026-10-09 04:41:01.382947

An approved withdrawal sets a participant to withdrawn and ends their pairs
as inactive. Both types predate Alembic and staging/prod were never checked
for 'inactive', so each value is added with IF NOT EXISTS and the three
environments converge. Autogenerate would rebuild approval_status through a
type swap and cannot see pair_status_enum at all, so the statements are
written out here.
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "63158db8a00a"
down_revision: Union[str, Sequence[str], None] = "9b3d1ba0df5e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add the two values. Nothing here uses them, so ADD VALUE inside the
    migration's transaction is allowed."""
    op.execute("ALTER TYPE approval_status ADD VALUE IF NOT EXISTS 'withdrawn'")
    op.execute("ALTER TYPE pair_status_enum ADD VALUE IF NOT EXISTS 'inactive'")


def downgrade() -> None:
    """No-op: Postgres cannot remove a value from an enum type."""
