from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.mentorship_enums import ParticipantNoteTag
from backend.entity.mentorship_participant_note_entity import (
    MentorshipParticipantNoteEntity,
)


@dataclass(frozen=True)
class TaggedNote:
    """When one tagged note was written about whom, in which round."""

    user_id: int
    round_id: int
    tag: ParticipantNoteTag
    created_at: datetime


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
        notification_stage: str | None = None,
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
            notification_stage (str | None): The notification a ``notified`` mark records.

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
            notification_stage=notification_stage,
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

    async def list_round_ids_by_tag(
        self, session: AsyncSession, user_ids: list[int], tag: ParticipantNoteTag
    ) -> dict[int, set[int]]:
        """The rounds each person carries a note with this tag in.

        Args:
            session (AsyncSession): The active async database session.
            user_ids (list[int]): The people.
            tag (ParticipantNoteTag): The tag.

        Returns:
            dict[int, set[int]]: user_id -> round_ids; people with none are
                left out.
        """
        if not user_ids:
            return {}
        result = await session.execute(
            select(
                MentorshipParticipantNoteEntity.user_id,
                MentorshipParticipantNoteEntity.round_id,
            )
            .where(
                MentorshipParticipantNoteEntity.user_id.in_(user_ids),
                MentorshipParticipantNoteEntity.tag == tag,
            )
            .distinct()
        )
        found: dict[int, set[int]] = {}
        for user_id, round_id in result.all():
            found.setdefault(user_id, set()).add(round_id)
        return found

    async def list_tagged(
        self,
        session: AsyncSession,
        user_ids: list[int],
        tags: list[ParticipantNoteTag],
    ) -> list[TaggedNote]:
        """Every note with one of these tags on any of these people, in one
        query.

        Args:
            session (AsyncSession): The active async database session.
            user_ids (list[int]): The people.
            tags (list[ParticipantNoteTag]): The tags.

        Returns:
            list[TaggedNote]: Oldest first.
        """
        if not user_ids or not tags:
            return []
        result = await session.execute(
            select(
                MentorshipParticipantNoteEntity.user_id,
                MentorshipParticipantNoteEntity.round_id,
                MentorshipParticipantNoteEntity.tag,
                MentorshipParticipantNoteEntity.created_at,
            )
            .where(
                MentorshipParticipantNoteEntity.user_id.in_(user_ids),
                MentorshipParticipantNoteEntity.tag.in_(tags),
            )
            .order_by(
                MentorshipParticipantNoteEntity.created_at,
                MentorshipParticipantNoteEntity.note_id,
            )
        )
        return [
            TaggedNote(user_id, round_id, tag, created_at)
            for user_id, round_id, tag, created_at in result.all()
        ]
