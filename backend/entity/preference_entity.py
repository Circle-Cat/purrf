from sqlalchemy import Boolean, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from backend.common.base import Base


class PreferenceEntity(Base):
    __tablename__ = "preferences"

    preferences_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"), index=True, unique=True
    )
    resume_guidance: Mapped[bool | None] = mapped_column(Boolean)
    career_path_guidance: Mapped[bool | None] = mapped_column(Boolean)
    experience_sharing: Mapped[bool | None] = mapped_column(Boolean)
    industry_trends: Mapped[bool | None] = mapped_column(Boolean)
    technical_skills: Mapped[bool | None] = mapped_column(Boolean)
    soft_skills: Mapped[bool | None] = mapped_column(Boolean)
    networking: Mapped[bool | None] = mapped_column(Boolean)
    project_management: Mapped[bool | None] = mapped_column(Boolean)
    specific_industry: Mapped[dict | None] = mapped_column(JSONB)
