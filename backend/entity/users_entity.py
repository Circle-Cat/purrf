from datetime import datetime
from sqlalchemy import Boolean, String, DateTime, func, Enum as SAEnum
from sqlalchemy.dialects.postgresql import ARRAY
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

    primary_email: Mapped[str] = mapped_column(String, unique=True)

    # text[] array
    alternative_emails: Mapped[list[str] | None] = mapped_column(ARRAY(String))

    linkedin_link: Mapped[str | None] = mapped_column(String)

    subject_identifier: Mapped[str] = mapped_column(
        String,
        unique=True,
    )

    is_active: Mapped[bool] = mapped_column(Boolean)

    updated_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), onupdate=func.now()
    )

    created_datetime: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
