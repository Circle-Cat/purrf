from datetime import datetime
from sqlalchemy import Boolean, String, DateTime, func, text, Enum as SAEnum
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
    # write-through synced by EmailManagementService so reads stay current. Drop
    # it once tools/primary_email_readiness.py reports the gap is ~0, then cut
    # the remaining reads over to user_emails and remove the sync.
    primary_email: Mapped[str] = mapped_column(String, unique=True)

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

    updated_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), onupdate=func.now()
    )

    created_datetime: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
