from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.approval_enums import ApprovalRequestStatus
from backend.common.base import Base


class ApprovalRequestEntity(Base):
    """One request for a named reviewer to approve something, whatever it is.

    The row records the approval and nothing about the thing approved: what
    it is about is ``target_type`` + ``target_id``, and anything else the
    action needs is in ``payload``. Which actions exist, who may review each
    and what approving one does live in the approval handlers, so a new
    action needs no migration. The price is that ``target_id`` carries no
    foreign key; a handler checks its target exists when the request is
    raised and again when it is approved.
    """

    __tablename__ = "approval_request"
    __table_args__ = (
        # A second pending request on the same target would let two
        # approvals of one thing both execute. The service checks first so
        # it can say so politely; this is what holds under a race.
        Index(
            "ux_approval_request_pending_target",
            "action",
            "target_type",
            "target_id",
            unique=True,
            postgresql_where=text("status = 'pending'"),
        ),
        Index("ix_approval_request_reviewer_status", "reviewer_id", "status"),
        Index("ix_approval_request_raised_by_status", "raised_by", "status"),
    )

    request_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    target_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_id: Mapped[str] = mapped_column(String(128), nullable=False)
    # Written once when the request is raised and never updated: what the
    # reviewer approves has to be what was asked for.
    payload: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    # Optional for every action: the raiser may give one, the reviewer
    # reads it.
    reason: Mapped[str | None] = mapped_column(String)
    raised_by: Mapped[int] = mapped_column(ForeignKey("users.user_id"), nullable=False)
    reviewer_id: Mapped[int] = mapped_column(
        ForeignKey("users.user_id"), nullable=False
    )
    status: Mapped[ApprovalRequestStatus] = mapped_column(
        Enum(
            ApprovalRequestStatus,
            name="approval_request_status_enum",
            values_callable=lambda o: [e.value for e in o],
        ),
        default=ApprovalRequestStatus.PENDING,
        server_default=ApprovalRequestStatus.PENDING.value,
        nullable=False,
    )
    # Whoever closed it: the reviewer for a decision, the raiser for a
    # withdrawal, the person who acted directly for a superseded one.
    decided_by: Mapped[int | None] = mapped_column(ForeignKey("users.user_id"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_comment: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
