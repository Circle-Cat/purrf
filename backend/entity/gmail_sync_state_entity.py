from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.base import Base


class GmailSyncStateEntity(Base):
    """Sync cursor and watch health for one Gmail mailbox, per environment.

    ``last_history_id`` is Gmail's mailbox-wide history cursor (uint64, hence
    BigInteger). It only moves forward, to the ``historyId`` of a
    ``history.list`` response whose changes were all processed. The integer
    ``id`` exists so notification events can point at this row.
    """

    __tablename__ = "gmail_sync_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email_address: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    last_history_id: Mapped[int | None] = mapped_column(BigInteger)
    watch_expiration: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_renewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_push_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    last_error_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_alert_kind: Mapped[str | None] = mapped_column(String(64))
    last_alert_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
