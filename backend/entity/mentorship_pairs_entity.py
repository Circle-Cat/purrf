from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import Integer, ForeignKey, Enum, CheckConstraint, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from backend.common.base import Base
from backend.common.mentorship_enums import PairStatus


class MentorshipPairsEntity(Base):
    __tablename__ = "mentorship_pairs"

    pair_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    round_id: Mapped[int] = mapped_column(ForeignKey("mentorship_round.round_id"))
    mentor_id: Mapped[int] = mapped_column(ForeignKey("users.user_id"))
    mentee_id: Mapped[int] = mapped_column(ForeignKey("users.user_id"))
    completed_count: Mapped[int] = mapped_column(Integer)
    status: Mapped[PairStatus] = mapped_column(
        Enum(
            PairStatus,
            name="pair_status_enum",
            values_callable=lambda obj: [e.value for e in obj],
        )
    )
    meeting_log: Mapped[dict | None] = mapped_column(JSONB)

    __table_args__ = (
        CheckConstraint("mentor_id <> mentee_id", name="check_different_ids"),
        UniqueConstraint("round_id", "mentor_id", "mentee_id"),
    )
