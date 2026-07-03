"""Replace job pending_form_schema/pending_pipeline_config/pending_profile_config with pending_payload

Revision ID: 70d81c883d0c
Revises: 95b36bb95db2
Create Date: 2026-07-02 09:02:12.095108

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "70d81c883d0c"
down_revision: Union[str, Sequence[str], None] = "95b36bb95db2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    connection = op.get_bind()
    in_flight = connection.execute(
        sa.text("SELECT job_id FROM job WHERE status = 'published_pending_revision'")
    ).fetchall()
    if in_flight:
        ids = ", ".join(str(row[0]) for row in in_flight)
        raise RuntimeError(
            f"Cannot migrate: job(s) {ids} have an in-flight PUBLISHED_PENDING_REVISION. "
            "Resolve (approve or reject) their pending review before running this migration."
        )
    op.add_column(
        "job",
        sa.Column(
            "pending_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
    )
    op.drop_column("job", "pending_form_schema")
    op.drop_column("job", "pending_pipeline_config")
    op.drop_column("job", "pending_profile_config")


def downgrade() -> None:
    """Recreate the three legacy pending columns (data is not restored)."""
    op.add_column(
        "job",
        sa.Column(
            "pending_form_schema",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "job",
        sa.Column(
            "pending_pipeline_config",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "job",
        sa.Column(
            "pending_profile_config",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.drop_column("job", "pending_payload")
