from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.entity.email_thread_entity import EmailThreadEntity


class EmailThreadRepository:
    """Database operations for EmailThreadEntity (one conversation per row).

    Domain-agnostic: callers pass ``context_type`` / ``context_id`` as plain
    values, so the same repository serves application, activity, employment,
    and broadcast threads.
    """

    async def create(
        self,
        session: AsyncSession,
        user_id: int,
        gmail_thread_id: str,
        subject: str | None,
        context_type: str,
        context_id: int | None,
    ) -> EmailThreadEntity:
        """Insert a new thread (called after Gmail accepts the first message).

        Args:
            session (AsyncSession): The active DB session.
            user_id (int): The person this conversation is with.
            gmail_thread_id (str): Gmail's thread id (unique).
            subject (str | None): The originating subject.
            context_type (str): A ``ContextType`` value (e.g. ``application``).
            context_id (int | None): The scenario entity id (e.g. application id).

        Returns:
            EmailThreadEntity: The created row (with ``thread_id`` populated).
        """
        entity = EmailThreadEntity(
            user_id=user_id,
            gmail_thread_id=gmail_thread_id,
            subject=subject,
            context_type=context_type,
            context_id=context_id,
        )
        session.add(entity)
        await session.flush()
        return entity

    async def get(
        self, session: AsyncSession, thread_id: int
    ) -> EmailThreadEntity | None:
        """Load a thread by primary key, or ``None`` if it does not exist.

        Args:
            session (AsyncSession): The active DB session.
            thread_id (int): The thread primary key.

        Returns:
            EmailThreadEntity | None: The matching thread, if any.
        """
        return await session.get(EmailThreadEntity, thread_id)

    async def get_by_gmail_thread_id(
        self, session: AsyncSession, gmail_thread_id: str
    ) -> EmailThreadEntity | None:
        """Look up a thread by its Gmail thread id, or ``None`` if unknown.

        Args:
            session (AsyncSession): The active DB session.
            gmail_thread_id (str): Gmail's thread id.

        Returns:
            EmailThreadEntity | None: The matching thread, if any.
        """
        result = await session.execute(
            select(EmailThreadEntity).where(
                EmailThreadEntity.gmail_thread_id == gmail_thread_id
            )
        )
        return result.scalar_one_or_none()

    async def list_by_context(
        self, session: AsyncSession, context_type: str, context_id: int | None
    ) -> list[EmailThreadEntity]:
        """Every thread for one scenario (e.g. one application), oldest first.

        Args:
            session (AsyncSession): The active DB session.
            context_type (str): A ``ContextType`` value.
            context_id (int | None): The scenario entity id.

        Returns:
            list[EmailThreadEntity]: Ordered by ``created_at`` ascending, with
                ``thread_id`` as a stable tiebreaker.
        """
        result = await session.execute(
            select(EmailThreadEntity)
            .where(
                EmailThreadEntity.context_type == context_type,
                EmailThreadEntity.context_id == context_id,
            )
            .order_by(
                EmailThreadEntity.created_at.asc(),
                EmailThreadEntity.thread_id.asc(),
            )
        )
        return list(result.scalars().all())

    async def mark_synced(self, session: AsyncSession, thread_id: int) -> None:
        """Stamp ``synced_at`` to the DB clock after a successful sync.

        Args:
            session (AsyncSession): The active DB session.
            thread_id (int): The thread that was just synced.
        """
        await session.execute(
            update(EmailThreadEntity)
            .where(EmailThreadEntity.thread_id == thread_id)
            .values(synced_at=func.now())
        )
