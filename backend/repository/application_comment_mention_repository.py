from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.entity.application_comment_mention_entity import (
    ApplicationCommentMentionEntity,
)


class ApplicationCommentMentionRepository:
    """Database operations for ApplicationCommentMentionEntity (append-only)."""

    async def create_mentions(
        self,
        session: AsyncSession,
        comment_id: int,
        mentioned_user_ids: list[int],
    ) -> None:
        """Record one validated mention row per user id.

        Args:
            session (AsyncSession): The active DB session.
            comment_id (int): The comment carrying the mention(s).
            mentioned_user_ids (list[int]): The already-validated,
                de-duplicated user ids to record. A caller passing an
                empty list is a safe no-op.
        """
        for mentioned_user_id in mentioned_user_ids:
            session.add(
                ApplicationCommentMentionEntity(
                    comment_id=comment_id, mentioned_user_id=mentioned_user_id
                )
            )
        await session.flush()

    async def get_by_comment_ids(
        self, session: AsyncSession, comment_ids: list[int]
    ) -> list[ApplicationCommentMentionEntity]:
        """Every mention row across a batch of comments.

        Args:
            session (AsyncSession): The active DB session.
            comment_ids (list[int]): The comments to fetch mentions for. An
                empty list returns an empty result without querying.

        Returns:
            list[ApplicationCommentMentionEntity]: Unordered; the caller
                groups by comment_id.
        """
        if not comment_ids:
            return []
        result = await session.execute(
            select(ApplicationCommentMentionEntity).where(
                ApplicationCommentMentionEntity.comment_id.in_(comment_ids)
            )
        )
        return list(result.scalars().all())
