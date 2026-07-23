from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.base import Base


class EmailMessageEntity(Base):
    """One message inside an ``email_thread`` — outbound (sent by us) or inbound.

    Written after Gmail confirms an outbound send, or on sync for inbound
    replies, keyed by ``gmail_message_id`` for idempotent upsert. ``direction``
    is stored as :class:`~backend.common.communication_enums.EmailDirection`;
    the domain layer derives it (by comparing ``from_address`` to the company
    sender), so this row just records what the transport reported.

    HTML and plain bodies are stored separately: an outbound message always
    has HTML, while an inbound reply may carry only one of the two.
    ``to_addresses`` / ``cc_addresses`` hold the raw RFC 5322 header text (we
    only display them, and parsing headers into clean lists is fragile).
    """

    __tablename__ = "email_message"

    message_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    thread_id: Mapped[int] = mapped_column(
        ForeignKey("email_thread.thread_id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    gmail_message_id: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False
    )
    rfc822_message_id: Mapped[str | None] = mapped_column(String(998))
    direction: Mapped[str] = mapped_column(String, nullable=False)
    from_address: Mapped[str | None] = mapped_column(String(255))
    to_addresses: Mapped[str | None] = mapped_column(Text)
    cc_addresses: Mapped[str | None] = mapped_column(Text)
    subject: Mapped[str | None] = mapped_column(String(998))
    body_html: Mapped[str | None] = mapped_column(Text)
    body_text: Mapped[str | None] = mapped_column(Text)
    snippet: Mapped[str | None] = mapped_column(Text)
    sent_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.user_id", ondelete="SET NULL")
    )
    gmail_internal_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
