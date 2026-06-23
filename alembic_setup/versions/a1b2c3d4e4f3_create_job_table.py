"""create job table

Revision ID: a1b2c3d4e4f3
Revises: a1b2c3d4e3f2
Create Date: 2026-06-23 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e4f3"
down_revision: Union[str, None] = "a1b2c3d4e3f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    job_kind = sa.Enum("employment", "activity", name="job_kind_enum")
    job_status = sa.Enum("draft", "published", "closed", name="job_status_enum")
    job_mentorship_role = sa.Enum("mentor", "mentee", name="job_mentorship_role_enum")
    job_kind.create(op.get_bind(), checkfirst=True)
    job_status.create(op.get_bind(), checkfirst=True)
    job_mentorship_role.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "job",
        sa.Column("job_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("kind", job_kind, nullable=False),
        sa.Column("mentorship_role", job_mentorship_role, nullable=True),
        sa.Column("status", job_status, server_default="draft", nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("form_schema", postgresql.JSONB(), nullable=True),
        sa.Column("created_datetime", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_timestamp", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )


def downgrade() -> None:
    op.drop_table("job")
    sa.Enum(name="job_mentorship_role_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="job_status_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="job_kind_enum").drop(op.get_bind(), checkfirst=True)
