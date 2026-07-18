from datetime import datetime
from sqlalchemy import Boolean, Integer, String, DateTime, func, text, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column
from backend.common.base import Base
from backend.common.mentorship_enums import CommunicationMethod


class UsersEntity(Base):
    __tablename__ = "users"

    user_id: Mapped[int] = mapped_column(primary_key=True)

    first_name: Mapped[str] = mapped_column(String)
    last_name: Mapped[str] = mapped_column(String)
    preferred_name: Mapped[str | None] = mapped_column(String)

    timezone: Mapped[str] = mapped_column(String)

    timezone_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    communication_channel: Mapped[CommunicationMethod] = mapped_column(
        SAEnum(
            CommunicationMethod,
            name="communication_method",
            values_callable=lambda obj: [e.value for e in obj],
        )
    )

    has_mentorship_mentor_experience: Mapped[bool | None] = mapped_column(Boolean)

    # TODO(PUR-496): retire this column. The live "primary contact" is the
    # user_emails is_primary row; this legacy column is kept only as a fallback
    # for users who have not yet verified (no is_primary row yet) and is
    # write-through synced by EmailManagementService so reads stay current.
    # Relaxed to nullable + non-unique (uq_user_emails_email owns the global
    # invariant now) so the follow-up PR that stops writing it can run against
    # the same schema; that PR cuts the reads over and drops the column.
    primary_email: Mapped[str | None] = mapped_column(String)

    linkedin_link: Mapped[str | None] = mapped_column(String)

    is_active: Mapped[bool] = mapped_column(Boolean)

    # Identity-layer super-admin flag: resolves to the full
    # Permission set without expanding user_permissions rows.
    is_super_admin: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )

    is_blocked: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false"), default=False
    )

    # Audit trail for is_blocked, written only by the blacklist action.
    blocked_by: Mapped[int | None] = mapped_column(Integer)
    blocked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    blocked_reason: Mapped[str | None] = mapped_column(String)

    updated_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), onupdate=func.now()
    )

    created_datetime: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
