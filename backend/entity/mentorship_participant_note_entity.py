from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.base import Base
from backend.common.mentorship_enums import ParticipantNoteTag


class MentorshipParticipantNoteEntity(Base):
    """A remark or a mark on one person in one mentorship round.

    Anchored on ``(user_id, round_id)`` rather than on the registration row,
    so someone who has not registered can still be written about and a note
    does not go when a registration is deleted. A note without a ``tag`` is a
    plain remark; with one it is a mark the rest of the system reads, such as
    a status change or a matching exemption.

    Append only: nothing edits or deletes a note. A correction is a new note.
    """

    __tablename__ = "mentorship_participant_note"
    __table_args__ = (
        Index("ix_mentorship_participant_note_user_round", "user_id", "round_id"),
    )

    note_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False
    )
    round_id: Mapped[int] = mapped_column(
        ForeignKey("mentorship_round.round_id"), nullable=False
    )
    pair_id: Mapped[int | None] = mapped_column(ForeignKey("mentorship_pairs.pair_id"))
    tag: Mapped[ParticipantNoteTag | None] = mapped_column(
        Enum(
            ParticipantNoteTag,
            name="participant_note_tag_enum",
            values_callable=lambda o: [e.value for e in o],
        )
    )
    body: Mapped[str] = mapped_column(String, nullable=False)
    author_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.user_id"), nullable=False
    )
    # The approval request that produced this note, when one did.
    request_id: Mapped[int | None] = mapped_column(
        ForeignKey("approval_request.request_id")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
