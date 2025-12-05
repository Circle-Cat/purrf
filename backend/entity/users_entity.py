from datetime import datetime
from sqlalchemy import Boolean, String, DateTime, Enum as SAEnum
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column
from backend.common.base import Base
from backend.common.mentorship_enums import UserTimezone


class UsersEntity(Base):
    __tablename__ = "users"

    user_id: Mapped[int] = mapped_column(primary_key=True)

    first_name: Mapped[str] = mapped_column(String, nullable=False)
    last_name: Mapped[str] = mapped_column(String, nullable=False)
    preferred_name: Mapped[str | None] = mapped_column(String)

    timezone: Mapped[UserTimezone] = mapped_column(
        SAEnum(
            UserTimezone,
            name="user_timezone",
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
    )

    communication_channel: Mapped[str] = mapped_column(String, nullable=False)

    has_mentorship_mentor_experience: Mapped[bool | None] = mapped_column(Boolean)

    primary_email: Mapped[str] = mapped_column(String, nullable=False)

    # text[] array
    alternative_emails: Mapped[list[str] | None] = mapped_column(ARRAY(String))

    linkedin_link: Mapped[str | None] = mapped_column(String)

    subject_identifier: Mapped[str] = mapped_column(
        String,
        nullable=False,
        unique=True,
    )

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False)

    updated_timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False)
