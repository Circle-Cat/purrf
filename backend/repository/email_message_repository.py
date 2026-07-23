from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.entity.email_message_entity import EmailMessageEntity


class EmailMessageRepository:
    """Database operations for EmailMessageEntity (one message per row)."""

    async def create(
        self,
        session: AsyncSession,
        thread_id: int,
        gmail_message_id: str,
        direction: str,
        from_address: str | None = None,
        to_addresses: str | None = None,
        cc_addresses: str | None = None,
        subject: str | None = None,
        body_html: str | None = None,
        body_text: str | None = None,
        snippet: str | None = None,
        rfc822_message_id: str | None = None,
        sent_by_user_id: int | None = None,
        gmail_internal_date: datetime | None = None,
    ) -> EmailMessageEntity:
        """Insert one message row.

        Args:
            session (AsyncSession): The active DB session.
            thread_id (int): The owning thread.
            gmail_message_id (str): Gmail's message id (unique; upsert key).
            direction (str): An ``EmailDirection`` value.
            from_address..gmail_internal_date: Message fields (see entity).

        Returns:
            EmailMessageEntity: The created row (with ``message_id`` populated).
        """
        entity = EmailMessageEntity(
            thread_id=thread_id,
            gmail_message_id=gmail_message_id,
            direction=direction,
            from_address=from_address,
            to_addresses=to_addresses,
            cc_addresses=cc_addresses,
            subject=subject,
            body_html=body_html,
            body_text=body_text,
            snippet=snippet,
            rfc822_message_id=rfc822_message_id,
            sent_by_user_id=sent_by_user_id,
            gmail_internal_date=gmail_internal_date,
        )
        session.add(entity)
        await session.flush()
        return entity

    async def get_by_gmail_message_id(
        self, session: AsyncSession, gmail_message_id: str
    ) -> EmailMessageEntity | None:
        """Look up a message by its Gmail message id (idempotency check on sync).

        Args:
            session (AsyncSession): The active DB session.
            gmail_message_id (str): Gmail's message id.

        Returns:
            EmailMessageEntity | None: The matching message, if already stored.
        """
        result = await session.execute(
            select(EmailMessageEntity).where(
                EmailMessageEntity.gmail_message_id == gmail_message_id
            )
        )
        return result.scalar_one_or_none()

    async def list_by_thread(
        self, session: AsyncSession, thread_id: int
    ) -> list[EmailMessageEntity]:
        """Every message in a thread, oldest first.

        Args:
            session (AsyncSession): The active DB session.
            thread_id (int): The thread to read.

        Returns:
            list[EmailMessageEntity]: Oldest first. Ordered by
                ``COALESCE(gmail_internal_date, created_at)`` so a just-sent
                outbound message (no Gmail timestamp yet) still sorts by its
                insert time, with ``message_id`` as a stable tiebreaker.
        """
        result = await session.execute(
            select(EmailMessageEntity)
            .where(EmailMessageEntity.thread_id == thread_id)
            .order_by(
                func.coalesce(
                    EmailMessageEntity.gmail_internal_date,
                    EmailMessageEntity.created_at,
                ).asc(),
                EmailMessageEntity.message_id.asc(),
            )
        )
        return list(result.scalars().all())
