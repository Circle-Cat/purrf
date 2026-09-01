"""add scorm course catalogue tables

Courses stop being four hard-coded enum values and become rows. The four that
exist keep working unchanged: they are seeded here as rows carrying their
category, and every existing `training` row is pointed at the one matching its
own category, so registration and the mentorship matching gate -- which filter
on `training.category` -- read exactly what they read before.

`training.category` becomes nullable in the same step. It has to: a course
created from the admin page has no category, and assignments to it would
otherwise be impossible to insert. Existing rows are untouched and keep theirs.

Revision ID: a8d31f74c260
Revises: f9206b0d6531
Create Date: 2026-09-01 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "a8d31f74c260"
down_revision: Union[str, Sequence[str], None] = "f9206b0d6531"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Seeded one-for-one with backend.common.mentorship_enums.TrainingCategory.
# Names are what an admin sees in the course list, so they are written for a
# reader rather than copied from the enum value.
_SEED_COURSES = [
    ("mentorship_mentee_onboarding", "Mentee Onboarding"),
    ("mentorship_mentor_onboarding", "Mentor Onboarding"),
    ("residency_program_onboarding", "Residency Program Onboarding"),
    ("corporate_culture_course", "Corporate Culture"),
]


def upgrade() -> None:
    """Upgrade schema."""
    sa.Enum("1.2", "2004", name="scorm_version").create(op.get_bind())

    op.create_table(
        "training_course",
        sa.Column("course_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column(
            "category",
            postgresql.ENUM(
                "mentorship_mentee_onboarding",
                "mentorship_mentor_onboarding",
                "residency_program_onboarding",
                "corporate_culture_course",
                name="training_category",
                create_type=False,
            ),
            nullable=True,
        ),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.Column("storage_prefix", sa.String(), nullable=True),
        sa.Column("entry_path", sa.String(), nullable=True),
        sa.Column(
            "scorm_version",
            postgresql.ENUM("1.2", "2004", name="scorm_version", create_type=False),
            nullable=True,
        ),
        sa.Column("package_version", sa.String(), nullable=True),
        sa.Column("reporting_mode", sa.String(), nullable=True),
        sa.Column("package_uploaded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verified_completable_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verified_by_user_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_datetime",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["verified_by_user_id"],
            ["users.user_id"],
            name=op.f("fk_training_course_verified_by_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("course_id", name=op.f("pk_training_course")),
        # One seed row per enum value, and no second course claiming a
        # category. NULL is not constrained, so any number of new courses can
        # exist without one.
        sa.UniqueConstraint("category", name=op.f("uq_training_course_category")),
    )

    for value, name in _SEED_COURSES:
        op.execute(
            sa.text(
                "INSERT INTO training_course (name, category, is_active) "
                "VALUES (:name, CAST(:category AS training_category), true)"
            ).bindparams(name=name, category=value)
        )

    op.add_column("training", sa.Column("course_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        op.f("fk_training_course_id_training_course"),
        "training",
        "training_course",
        ["course_id"],
        ["course_id"],
        # RESTRICT, not CASCADE: nothing deletes a course, and if something
        # ever tries, losing people's completion records with it would be the
        # worst possible way to find out.
        ondelete="RESTRICT",
    )
    op.create_index(
        op.f("ix_training_course_id"), "training", ["course_id"], unique=False
    )

    # Point every existing assignment at its seed course.
    op.execute(
        "UPDATE training SET course_id = training_course.course_id "
        "FROM training_course "
        "WHERE training_course.category = training.category"
    )

    # Partial, so the four seed rows' many NULLs before this backfill -- and
    # any future row without a course -- do not collide with each other.
    op.create_index(
        "uq_training_user_course",
        "training",
        ["user_id", "course_id"],
        unique=True,
        postgresql_where=sa.text("course_id IS NOT NULL"),
    )

    op.alter_column(
        "training",
        "category",
        existing_type=postgresql.ENUM(
            "mentorship_mentee_onboarding",
            "mentorship_mentor_onboarding",
            "residency_program_onboarding",
            "corporate_culture_course",
            name="training_category",
        ),
        nullable=True,
    )

    op.create_table(
        "training_progress",
        sa.Column("progress_id", sa.Integer(), nullable=False),
        sa.Column("training_id", sa.Integer(), nullable=False),
        sa.Column("lesson_status", sa.String(), nullable=True),
        sa.Column("lesson_location", sa.String(), nullable=True),
        # 🔴 Text, deliberately unbounded. Real packages disable the SCORM 1.2
        # 4096-character limit and write past it; a rejected write is invisible
        # to the course and costs the learner their place. Never add a length.
        sa.Column("suspend_data", sa.Text(), nullable=True),
        sa.Column("score_raw", sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column("score_min", sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column("score_max", sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column(
            "session_time_seconds",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("last_accessed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_datetime",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["training_id"],
            ["training.training_id"],
            name=op.f("fk_training_progress_training_id_training"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("progress_id", name=op.f("pk_training_progress")),
        sa.UniqueConstraint(
            "training_id", name=op.f("uq_training_progress_training_id")
        ),
    )


def downgrade() -> None:
    """Downgrade schema.

    Restoring `training.category` to NOT NULL fails if any assignment to a
    course without a category exists. That is intended: those rows have no
    category to restore, and inventing one would corrupt the matching gate.
    Delete them first if a downgrade is genuinely wanted.
    """
    op.drop_table("training_progress")

    op.alter_column(
        "training",
        "category",
        existing_type=postgresql.ENUM(
            "mentorship_mentee_onboarding",
            "mentorship_mentor_onboarding",
            "residency_program_onboarding",
            "corporate_culture_course",
            name="training_category",
        ),
        nullable=False,
    )

    op.drop_index("uq_training_user_course", table_name="training")
    op.drop_index(op.f("ix_training_course_id"), table_name="training")
    op.drop_constraint(
        op.f("fk_training_course_id_training_course"), "training", type_="foreignkey"
    )
    op.drop_column("training", "course_id")

    op.drop_table("training_course")
    sa.Enum(name="scorm_version").drop(op.get_bind())
