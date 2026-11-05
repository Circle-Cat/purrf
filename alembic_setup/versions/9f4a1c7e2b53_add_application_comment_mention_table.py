"""add application_comment_mention table

Revision ID: 9f4a1c7e2b53
Revises: 3186f77c39e6
Create Date: 2026-07-08 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9f4a1c7e2b53"
down_revision: Union[str, Sequence[str], None] = "3186f77c39e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "application_comment_mention",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("comment_id", sa.Integer(), nullable=False),
        sa.Column("mentioned_user_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["comment_id"],
            ["application_comment.comment_id"],
            name=op.f("fk_application_comment_mention_comment_id_application_comment"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["mentioned_user_id"],
            ["users.user_id"],
            name=op.f("fk_application_comment_mention_mentioned_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_application_comment_mention")),
        sa.UniqueConstraint(
            "comment_id",
            "mentioned_user_id",
            name=op.f("uq_application_comment_mention_comment_id"),
        ),
    )
    op.create_index(
        op.f("ix_application_comment_mention_comment_id"),
        "application_comment_mention",
        ["comment_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_application_comment_mention_mentioned_user_id"),
        "application_comment_mention",
        ["mentioned_user_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        op.f("ix_application_comment_mention_mentioned_user_id"),
        table_name="application_comment_mention",
    )
    op.drop_index(
        op.f("ix_application_comment_mention_comment_id"),
        table_name="application_comment_mention",
    )
    op.drop_table("application_comment_mention")
