from sqlalchemy import Float, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from backend.common.base import Base


class MentorshipRoundEntity(Base):
    __tablename__ = "mentorship_round"

    round_id: Mapped[int] = mapped_column(Integer, primary_key=True)

    name: Mapped[str] = mapped_column(String)
    mentee_average_score: Mapped[float | None] = mapped_column(Float)
    mentor_average_score: Mapped[float | None] = mapped_column(Float)
    expectations: Mapped[str | None] = mapped_column(String)
    description: Mapped[dict | None] = mapped_column(JSONB)
    required_meetings: Mapped[int] = mapped_column(Integer, default=5)
