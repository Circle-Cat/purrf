from datetime import datetime
from sqlalchemy import DateTime, Enum, ForeignKey, Integer, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from backend.common.base import Base
from backend.common.recruiting_enums import ApplicationStage


class ApplicationAssignmentEntity(Base):
    """The interviewer currently responsible for one application's stage.

    One active row per (application_id, stage) — reassigning overwrites the
    row rather than appending history; the outgoing assignee's `evaluation`
    row (sub-project #3 slice 1) survives independently, keyed by its own
    evaluator_id.
    """

    __tablename__ = "application_assignment"
    __table_args__ = (
        UniqueConstraint(
            "application_id", "stage", name="uq_application_assignment_app_stage"
        ),
    )

    assignment_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    application_id: Mapped[int] = mapped_column(
        ForeignKey("application.application_id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    stage: Mapped[ApplicationStage] = mapped_column(
        Enum(
            ApplicationStage,
            name="application_stage_enum",
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
    )
    assignee_id: Mapped[int] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"), index=True, nullable=False
    )
    assigned_by: Mapped[int] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
