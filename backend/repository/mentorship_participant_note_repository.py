from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.mentorship_enums import ParticipantNoteTag
from backend.entity.mentorship_participant_note_entity import (
    MentorshipParticipantNoteEntity,
)


class MentorshipParticipantNoteRepository:
    """
    Repository for mentorship_participant_note rows. Append only: there is no
    update or delete, because a note is a record of what someone said at the
    time and a correction is a new note.
    """

    async def create(
        self,
        session: AsyncSession,
        *,
        user_id: int,
        round_id: int,
        author_user_id: int,
        body: str,
        tag: ParticipantNoteTag | None = None,
        pair_id: int | None = None,
        request_id: int | None = None,
    ) -> MentorshipParticipantNoteEntity:
        """
        Add a note. Does not commit -- the calling service owns the
        transaction, which is what lets a status change and its note land
        together or not at all.

        Args:
            session (AsyncSession): The active async database session.
            user_id (int): Who the note is about.
            round_id (int): Which round it belongs to.
            author_user_id (int): Who wrote it.
            body (str): What it says.
            tag (ParticipantNoteTag | None): What kind of mark it is, or None
                for a plain remark.
            pair_id (int | None): The pair it is about, when it is about one.
            request_id (int | None): The approval request that produced it.

        Returns:
            MentorshipParticipantNoteEntity: The new row.
        """
        row = MentorshipParticipantNoteEntity(
            user_id=user_id,
            round_id=round_id,
            author_user_id=author_user_id,
            body=body,
            tag=tag,
            pair_id=pair_id,
            request_id=request_id,
        )
        session.add(row)
        await session.flush()
        return row

    async def list_for_user_round(
        self, session: AsyncSession, user_id: int, round_id: int
    ) -> list[MentorshipParticipantNoteEntity]:
        """
        Every note on one person in one round.

        Args:
            session (AsyncSession): The active async database session.
            user_id (int): Who the notes are about.
            round_id (int): Which round.

        Returns:
            list[MentorshipParticipantNoteEntity]: Oldest first.
        """
        result = await session.execute(
            select(MentorshipParticipantNoteEntity)
            .where(
                MentorshipParticipantNoteEntity.user_id == user_id,
                MentorshipParticipantNoteEntity.round_id == round_id,
            )
            .order_by(
                MentorshipParticipantNoteEntity.created_at,
                MentorshipParticipantNoteEntity.note_id,
            )
        )
        return list(result.scalars().all())
