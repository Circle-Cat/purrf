from sqlalchemy import (
    BigInteger,
    Enum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.base import Base
from backend.common.mentorship_email_enums import MentorshipEmailRecipientResult


class MentorshipEmailRecipientEntity(Base):
    __tablename__ = "mentorship_email_recipient"
    __table_args__ = (UniqueConstraint("send_id", "user_id"),)

    recipient_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    send_id: Mapped[int] = mapped_column(
        ForeignKey("mentorship_email_send.send_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.user_id"), nullable=False, index=True
    )
    email: Mapped[str | None] = mapped_column(String(320))
    kit_subscriber_id: Mapped[int | None] = mapped_column(BigInteger)
    result: Mapped[MentorshipEmailRecipientResult] = mapped_column(
        Enum(
            MentorshipEmailRecipientResult,
            name="mentorship_email_recipient_result_enum",
            values_callable=lambda o: [e.value for e in o],
        ),
        default=MentorshipEmailRecipientResult.PENDING,
        server_default=MentorshipEmailRecipientResult.PENDING.value,
        nullable=False,
    )
    failure_reason: Mapped[str | None] = mapped_column(String(255))
