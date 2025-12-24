from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Integer, ForeignKey, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB
from backend.common.base import Base


class ExperienceEntity(Base):
    __tablename__ = "experience"

    experience_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id"), unique=True)
    education: Mapped[list[dict] | None] = mapped_column(JSONB)
    work_history: Mapped[list[dict] | None] = mapped_column(JSONB)
    updated_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), onupdate=func.now()
    )
