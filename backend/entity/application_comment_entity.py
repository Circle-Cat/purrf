from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.base import Base


class ApplicationCommentEntity(Base):
    """One append-only, free-text comment on an application.

    Written by BoardService.add_comment (owner or current-stage assignee);
    never updated or deleted once written. Independent of
    ApplicationActivityEntity -- this is discussion, not an audit log.
    """

    __tablename__ = "application_comment"

    comment_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    application_id: Mapped[int] = mapped_column(
        ForeignKey("application.application_id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    author_id: Mapped[int] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False
    )
    body: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
