from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.base import Base


class EmailThreadEntity(Base):
    """One email conversation with a person (``users.user_id``), tagged by scenario.

    A thread is anchored to a person and carries a ``(context_type,
    context_id)`` tag saying which relationship it is about — an application,
    an activity, an employment, or a broadcast. The recruiting Emails tab
    lists threads by ``(context_type=APPLICATION, context_id=application_id)``.

    ``context_id`` is a deliberately polymorphic reference (it points into a
    different table depending on ``context_type``), so it carries **no**
    database-level foreign key; keeping it consistent is the caller's job.

    A row is created only after Gmail accepts the first outbound message, so
    ``gmail_thread_id`` is always known and non-null.
    """

    __tablename__ = "email_thread"

    thread_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"), index=True, nullable=False
    )
    gmail_thread_id: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False
    )
    subject: Mapped[str | None] = mapped_column(String(998))
    context_type: Mapped[str] = mapped_column(String, nullable=False)
    context_id: Mapped[int | None] = mapped_column(Integer)
    synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        # The recruiting view filters by (context_type, context_id); lead the
        # index with those. user_id keeps its own index (declared above) for
        # future person-centric queries.
        Index("ix_email_thread_context", "context_type", "context_id"),
    )
