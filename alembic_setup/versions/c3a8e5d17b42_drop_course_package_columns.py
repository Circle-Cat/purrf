"""drop the course's own package columns

The package is a row now. These columns were the same facts held one course
at a time, which is why an upload had to remember to clear the verification
stamp; nothing reads them any more.

Revision ID: c3a8e5d17b42
Revises: b7f2c1a94e08
Create Date: 2026-09-04 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "c3a8e5d17b42"
down_revision: Union[str, Sequence[str], None] = "b7f2c1a94e08"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_column("training_course", "verified_by_user_id")
    op.drop_column("training_course", "verified_completable_at")
    op.drop_column("training_course", "package_uploaded_at")
    op.drop_column("training_course", "reporting_mode")
    op.drop_column("training_course", "package_version")
    op.drop_column("training_course", "scorm_version")
    op.drop_column("training_course", "entry_path")
    op.drop_column("training_course", "storage_prefix")


def downgrade() -> None:
    """Downgrade schema.

    The columns come back empty. What they held lives in
    training_course_package, and this revision does not put it back.
    """
    op.add_column(
        "training_course", sa.Column("storage_prefix", sa.String(), nullable=True)
    )
    op.add_column(
        "training_course", sa.Column("entry_path", sa.String(), nullable=True)
    )
    op.add_column(
        "training_course",
        sa.Column(
            "scorm_version",
            postgresql.ENUM("1.2", "2004", name="scorm_version", create_type=False),
            nullable=True,
        ),
    )
    op.add_column(
        "training_course", sa.Column("package_version", sa.String(), nullable=True)
    )
    op.add_column(
        "training_course", sa.Column("reporting_mode", sa.String(), nullable=True)
    )
    op.add_column(
        "training_course",
        sa.Column("package_uploaded_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "training_course",
        sa.Column("verified_completable_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "training_course",
        sa.Column("verified_by_user_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_training_course_verified_by_user_id_users",
        "training_course",
        "users",
        ["verified_by_user_id"],
        ["user_id"],
        ondelete="SET NULL",
    )
