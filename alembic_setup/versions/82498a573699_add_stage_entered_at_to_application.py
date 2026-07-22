"""add stage_entered_at to application

Revision ID: 82498a573699
Revises: b78bd7956d7a
Create Date: 2026-07-22 09:12:35.207305

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '82498a573699'
down_revision: Union[str, Sequence[str], None] = 'b78bd7956d7a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. Add nullable first so existing rows don't violate NOT NULL.
    op.add_column(
        "application",
        sa.Column("stage_entered_at", sa.DateTime(timezone=True), nullable=True),
    )
    # 2. Backfill: the entry time for a row's CURRENT stage is the latest
    #    activity that represents entering that stage — a 'blacklisted' event
    #    (stage becomes rejected) or a 'stage_changed' whose toStage == the
    #    row's stage. Rows that only ever auto-landed have neither → fall back
    #    to created_datetime (== submit == entry time for an auto-screen).
    op.execute(
        """
        UPDATE application AS app
        SET stage_entered_at = COALESCE(
            (SELECT max(act.created_at)
               FROM application_activity AS act
              WHERE act.application_id = app.application_id
                AND (act.event_type = 'blacklisted'
                     OR (act.event_type = 'stage_changed'
                         AND act.details->>'toStage' = app.stage::text))),
            app.created_datetime
        )
        """
    )
    # 3. Now every row has a value; enforce NOT NULL + server default.
    op.alter_column(
        "application",
        "stage_entered_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )
    # 4. Index covering the terminal-page WHERE + full ORDER BY.
    op.create_index(
        "ix_application_job_stage_entered",
        "application",
        ["job_id", "stage", sa.text("stage_entered_at DESC"), sa.text("application_id DESC")],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_application_job_stage_entered", table_name="application")
    op.drop_column("application", "stage_entered_at")
