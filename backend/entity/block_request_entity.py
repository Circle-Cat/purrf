from datetime import datetime
from sqlalchemy import String, Integer, Enum, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column
from backend.common.base import Base
from backend.common.user_enums import BlockRequestStatus


class BlockRequestEntity(Base):
    """One request to block a user, raised from a domain page, decided by the
    named USER_ADMIN holder. Only the named reviewer may decide it; only the
    raiser may reassign it."""

    __tablename__ = "block_request"

    request_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    target_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.user_id"), nullable=False
    )
    raised_by: Mapped[int] = mapped_column(ForeignKey("users.user_id"), nullable=False)
    # Which domain page the request came from, e.g. "recruiting_board".
    # Display only -- authorization comes from the permission gate, not this.
    raised_from: Mapped[str] = mapped_column(String(64), nullable=False)
    reason: Mapped[str] = mapped_column(String, nullable=False)
    reviewer_id: Mapped[int] = mapped_column(
        ForeignKey("users.user_id"), nullable=False
    )
    status: Mapped[BlockRequestStatus] = mapped_column(
        Enum(
            BlockRequestStatus,
            name="block_request_status_enum",
            values_callable=lambda o: [e.value for e in o],
        ),
        default=BlockRequestStatus.PENDING,
        server_default=BlockRequestStatus.PENDING.value,
        nullable=False,
    )
    decided_by: Mapped[int | None] = mapped_column(ForeignKey("users.user_id"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_note: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
