from datetime import datetime
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column
from backend.common.base import Base


class UserEmailsEntity(Base):
    __tablename__ = "user_emails"

    email_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id"))

    email: Mapped[str] = mapped_column(String(255))

    otp_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)

    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)

    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        # Kept although implied by uq_user_emails_email: its (user_id, email)
        # btree doubles as the index for user_id lookups.
        UniqueConstraint(
            "user_id",
            "email",
            name="uq_user_emails_user_id_email",
        ),
        Index(
            "user_emails_primary_idx",
            "user_id",
            unique=True,
            postgresql_where=text("is_primary"),
        ),
        CheckConstraint(
            "NOT is_primary OR otp_confirmed",
            name="user_emails_primary_must_be_confirmed",
        ),
        # An address belongs to at most one account, confirmed or not. This
        # carries the global one-email-one-account invariant (and the
        # concurrent first-login race guard) that historically lived on
        # users.primary_email's unique constraint, so that column can be
        # retired.
        UniqueConstraint("email", name="uq_user_emails_email"),
    )
