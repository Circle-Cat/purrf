"""add training retired prefix

An overwrite writes the new package to a fresh prefix and flips the course over
to it, leaving the old files in place. They cannot be deleted at once: a
resource request can be in flight across the switch, and content tokens stay
valid for twelve hours after they are issued. This table is the list of
prefixes waiting out that delay.

Revision ID: b614c0d9e3a7
Revises: a8d31f74c260
Create Date: 2026-09-01 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b614c0d9e3a7"
down_revision: Union[str, Sequence[str], None] = "a8d31f74c260"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "training_retired_prefix",
        sa.Column("retired_prefix_id", sa.Integer(), nullable=False),
        sa.Column("course_id", sa.Integer(), nullable=False),
        sa.Column("storage_prefix", sa.String(), nullable=False),
        sa.Column("delete_after", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_datetime",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["course_id"],
            ["training_course.course_id"],
            name=op.f("fk_training_retired_prefix_course_id_training_course"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "retired_prefix_id", name=op.f("pk_training_retired_prefix")
        ),
        # A prefix is a fresh uuid per upload, so a repeat means the same
        # overwrite was recorded twice.
        sa.UniqueConstraint(
            "storage_prefix", name=op.f("uq_training_retired_prefix_storage_prefix")
        ),
    )
    op.create_index(
        op.f("ix_training_retired_prefix_course_id"),
        "training_retired_prefix",
        ["course_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_training_retired_prefix_delete_after"),
        "training_retired_prefix",
        ["delete_after"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema.

    Drops the record of which prefixes are pending deletion. The objects
    themselves stay in the bucket and would have to be removed by hand.
    """
    op.drop_index(
        op.f("ix_training_retired_prefix_delete_after"),
        table_name="training_retired_prefix",
    )
    op.drop_index(
        op.f("ix_training_retired_prefix_course_id"),
        table_name="training_retired_prefix",
    )
    op.drop_table("training_retired_prefix")
