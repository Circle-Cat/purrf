from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.entity.application_comment_entity import ApplicationCommentEntity


class ApplicationCommentRepository:
    """Database operations for ApplicationCommentEntity (append-only)."""

    async def create(
        self,
        session: AsyncSession,
        application_id: int,
        author_id: int,
        body: str,
    ) -> ApplicationCommentEntity:
        """Append one comment to an application's discussion thread.

        Args:
            session (AsyncSession): The active DB session.
            application_id (int): The application this comment is on.
            author_id (int): The user who wrote the comment.
            body (str): The comment text.

        Returns:
            ApplicationCommentEntity: The created row.
        """
        entity = ApplicationCommentEntity(
            application_id=application_id,
            author_id=author_id,
            body=body,
        )
        session.add(entity)
        await session.flush()
        return entity

    async def list_by_application(
        self, session: AsyncSession, application_id: int
    ) -> list[ApplicationCommentEntity]:
        """Every comment on one application, newest first.

        Args:
            session (AsyncSession): The active DB session.
            application_id (int): The application to fetch comments for.

        Returns:
            list[ApplicationCommentEntity]: Ordered by created_at descending,
                falling back to comment_id descending to break ties between
                comments written within the same DB timestamp tick.
        """
        result = await session.execute(
            select(ApplicationCommentEntity)
            .where(ApplicationCommentEntity.application_id == application_id)
            .order_by(
                ApplicationCommentEntity.created_at.desc(),
                ApplicationCommentEntity.comment_id.desc(),
            )
        )
        return list(result.scalars().all())
