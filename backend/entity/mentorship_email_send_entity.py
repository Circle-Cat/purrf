from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.base import Base
from backend.common.mentorship_email_enums import MentorshipEmailSendStatus


class MentorshipEmailSendEntity(Base):
    """One Kit broadcast prepared from Purrf: a copy of a draft the business wrote
    in Kit, aimed at this send's tag. preview_html is what the admin approved,
    kept as the record of what was sent."""

    __tablename__ = "mentorship_email_send"

    send_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    round_id: Mapped[int] = mapped_column(
        ForeignKey("mentorship_round.round_id"), nullable=False
    )
    stage: Mapped[str] = mapped_column(String(32), nullable=False)
    kit_draft_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    kit_draft_subject: Mapped[str] = mapped_column(String(500), nullable=False)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.user_id"), nullable=False)
    status: Mapped[MentorshipEmailSendStatus] = mapped_column(
        Enum(
            MentorshipEmailSendStatus,
            name="mentorship_email_send_status_enum",
            values_callable=lambda o: [e.value for e in o],
        ),
        default=MentorshipEmailSendStatus.DRAFT,
        server_default=MentorshipEmailSendStatus.DRAFT.value,
        nullable=False,
    )
    sender_address: Mapped[str] = mapped_column(String(255), nullable=False)
    kit_tag_name: Mapped[str] = mapped_column(String(255), nullable=False)
    kit_tag_id: Mapped[int | None] = mapped_column(BigInteger)
    kit_broadcast_id: Mapped[int | None] = mapped_column(BigInteger)
    prepare_claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)
    failure_code: Mapped[str | None] = mapped_column(String(32))
    preview_fingerprint: Mapped[str | None] = mapped_column(String(64))
    preview_subject: Mapped[str | None] = mapped_column(String(500))
    preview_html: Mapped[str | None] = mapped_column(Text)
    kit_recipient_count: Mapped[int | None] = mapped_column(Integer)
    send_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    tag_deleted: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
