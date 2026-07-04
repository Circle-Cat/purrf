from datetime import datetime
from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from backend.common.base import Base
from backend.common.recruiting_enums import ApplicationStage


class EvaluationEntity(Base):
    """One evaluator's scorecard for one application's stage.

    Unique per (application_id, stage, evaluator_id) — a reassignment
    (application_assignment) leaves prior evaluators' rows untouched as
    history; a fresh assignee gets their own row when they start a draft.
    Immutable once is_confirmed=True (enforced in EvaluationRepository, not
    at the DB layer).
    """

    __tablename__ = "evaluation"
    __table_args__ = (
        UniqueConstraint(
            "application_id",
            "stage",
            "evaluator_id",
            name="uq_evaluation_app_stage_evaluator",
        ),
    )

    evaluation_id: Mapped[int] = mapped_column(
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
    evaluator_id: Mapped[int] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"), index=True, nullable=False
    )
    responses: Mapped[dict] = mapped_column(JSONB, default=dict)
    is_confirmed: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_datetime: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), onupdate=func.now()
    )
