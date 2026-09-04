"""add training_course_package

A package becomes a row so the verification stamp can live on the thing it is
a statement about. The course keeps its own package columns for now; a later
revision drops them once nothing reads them.

Revision ID: b7f2c1a94e08
Revises: a8d31f74c260
Create Date: 2026-09-04 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "b7f2c1a94e08"
down_revision: Union[str, Sequence[str], None] = "a8d31f74c260"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    sa.Enum("live", "pending", name="training_package_state").create(op.get_bind())

    op.create_table(
        "training_course_package",
        sa.Column("package_id", sa.Integer(), nullable=False),
        sa.Column("course_id", sa.Integer(), nullable=False),
        sa.Column(
            "state",
            postgresql.ENUM(
                "live",
                "pending",
                name="training_package_state",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("storage_prefix", sa.String(), nullable=False),
        sa.Column("entry_path", sa.String(), nullable=False),
        sa.Column(
            "scorm_version",
            postgresql.ENUM("1.2", "2004", name="scorm_version", create_type=False),
            nullable=False,
        ),
        sa.Column("package_version", sa.String(), nullable=True),
        sa.Column("reporting_mode", sa.String(), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("uploaded_by_user_id", sa.Integer(), nullable=True),
        sa.Column("verified_completable_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verified_by_user_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["course_id"], ["training_course.course_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["uploaded_by_user_id"], ["users.user_id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["verified_by_user_id"], ["users.user_id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("package_id"),
    )
    op.create_index(
        "ix_training_course_package_course_id",
        "training_course_package",
        ["course_id"],
    )
    # Partial, so a course may hold one of each slot but never two of one.
    op.create_index(
        "ux_course_package_live",
        "training_course_package",
        ["course_id"],
        unique=True,
        postgresql_where=sa.text("state = 'live'"),
    )
    op.create_index(
        "ux_course_package_pending",
        "training_course_package",
        ["course_id"],
        unique=True,
        postgresql_where=sa.text("state = 'pending'"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ux_course_package_pending", table_name="training_course_package")
    op.drop_index("ux_course_package_live", table_name="training_course_package")
    op.drop_index(
        "ix_training_course_package_course_id", table_name="training_course_package"
    )
    op.drop_table("training_course_package")
    sa.Enum(name="training_package_state").drop(op.get_bind())
