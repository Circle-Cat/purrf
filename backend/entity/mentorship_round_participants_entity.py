import uuid
from sqlalchemy import (
    Boolean,
    Integer,
    String,
    Uuid,
    Enum,
    UniqueConstraint,
    ForeignKey,
)
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from sqlalchemy.orm import Mapped, mapped_column
from backend.common.mentorship_enums import ApprovalStatus, ParticipantRole
from backend.common.base import Base


class MentorshipRoundParticipantsEntity(Base):
    __tablename__ = "mentorship_round_participants"

    participant_id: Mapped[uuid] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE")
    )
    match_email_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    round_id: Mapped[int] = mapped_column(ForeignKey("mentorship_round.round_id"))
    max_partners: Mapped[int] = mapped_column(Integer, default=1)
    approval_status: Mapped[ApprovalStatus | None] = mapped_column(
        Enum(
            ApprovalStatus,
            name="approval_status",
            values_callable=lambda obj: [e.value for e in obj],
        )
    )
    participant_role: Mapped[ParticipantRole | None] = mapped_column(
        Enum(
            ParticipantRole,
            name="participant_role",
            values_callable=lambda obj: [e.value for e in obj],
        )
    )
    pair_feedback: Mapped[dict | None] = mapped_column(JSONB)
    program_feedback: Mapped[str | None] = mapped_column(String)
    expected_partner_user_id: Mapped[list[int] | None] = mapped_column(ARRAY(Integer))
    unexpected_partner_user_id: Mapped[list[int] | None] = mapped_column(ARRAY(Integer))
    goal: Mapped[str | None] = mapped_column(String(300))

    __table_args__ = (UniqueConstraint("round_id", "user_id"),)
