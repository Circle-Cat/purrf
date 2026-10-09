from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import defer

from backend.entity.email_message_entity import EmailMessageEntity


class EmailMessageRepository:
    """Database operations for EmailMessageEntity (one message per row)."""

    async def insert_or_get(
        self,
        session: AsyncSession,
        thread_id: int,
        gmail_message_id: str,
        direction: str,
        from_address: str | None = None,
        to_addresses: str | None = None,
        subject: str | None = None,
        body_html: str | None = None,
        body_text: str | None = None,
        snippet: str | None = None,
        rfc822_message_id: str | None = None,
        sent_by_user_id: int | None = None,
        gmail_internal_date: datetime | None = None,
        failed_recipients: str | None = None,
        inbound_kind: str | None = None,
        attachments: list[dict] | None = None,
    ) -> tuple[EmailMessageEntity, bool]:
        """Insert one message row, or read the one already stored under its id.

        A message we send can be stored twice at once: by the send that wrote
        it and by a Gmail sync that read it back. ``ON CONFLICT DO NOTHING``
        waits for the other writer and then skips instead of raising, so
        neither transaction fails; the select afterwards sees the other row
        once it has committed.

        Args:
            session (AsyncSession): The active DB session.
            thread_id (int): The owning thread.
            gmail_message_id (str): Gmail's message id (unique).
            direction (str): An ``EmailDirection`` value.
            from_address..attachments: Message fields (see entity).

        Returns:
            tuple[EmailMessageEntity, bool]: The row, and True when this call
                inserted it; False means it was already stored and the fields
                passed here were not applied.
        """
        fields = {
            "thread_id": thread_id,
            "gmail_message_id": gmail_message_id,
            "direction": direction,
            "from_address": from_address,
            "to_addresses": to_addresses,
            "subject": subject,
            "body_html": body_html,
            "body_text": body_text,
            "snippet": snippet,
            "rfc822_message_id": rfc822_message_id,
            "sent_by_user_id": sent_by_user_id,
            "gmail_internal_date": gmail_internal_date,
            "failed_recipients": failed_recipients,
            "inbound_kind": inbound_kind,
            "attachments": attachments,
        }
        # Omitted rather than bound as None: a None bound to the JSONB column
        # would store JSON null instead of SQL NULL.
        values = {key: value for key, value in fields.items() if value is not None}
        inserted = await session.scalar(
            insert(EmailMessageEntity)
            .values(**values)
            .on_conflict_do_nothing(index_elements=["gmail_message_id"])
            .returning(EmailMessageEntity)
        )
        if inserted is not None:
            return inserted, True
        existing = await session.scalar(
            select(EmailMessageEntity).where(
                EmailMessageEntity.gmail_message_id == gmail_message_id
            )
        )
        return existing, False

    async def list_gmail_message_ids_by_thread(
        self, session: AsyncSession, thread_id: int
    ) -> set[str]:
        """The Gmail message ids already stored for one thread.

        One query answers "which of these did we already save?" for a whole
        thread, so an incremental sync costs a single round trip per thread
        instead of one per message.

        Args:
            session (AsyncSession): The active DB session.
            thread_id (int): The thread to read.

        Returns:
            set[str]: The stored ``gmail_message_id``s (empty if none).
        """
        result = await session.execute(
            select(EmailMessageEntity.gmail_message_id).where(
                EmailMessageEntity.thread_id == thread_id
            )
        )
        return set(result.scalars().all())

    async def list_sender_ids_by_thread(
        self, session: AsyncSession, thread_id: int
    ) -> set[int]:
        """The users who sent a message in one thread through Purrf.

        Only outbound messages carry a sender, and only when Purrf sent them;
        one sent by hand from the Gmail web UI has none.

        Args:
            session (AsyncSession): The active DB session.
            thread_id (int): The thread to read.

        Returns:
            set[int]: The distinct ``sent_by_user_id``s (empty if none).
        """
        result = await session.execute(
            select(EmailMessageEntity.sent_by_user_id)
            .where(
                EmailMessageEntity.thread_id == thread_id,
                EmailMessageEntity.sent_by_user_id.is_not(None),
            )
            .distinct()
        )
        return set(result.scalars().all())

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

    async def list_by_threads(
        self, session: AsyncSession, thread_ids: list[int]
    ) -> dict[int, list[EmailMessageEntity]]:
        """Every message of several threads in one query, each thread oldest first.

        Bodies are not loaded: rows and counts never show them, and
        ``list_by_thread`` reads them for the one thread that is opened.

        Args:
            session (AsyncSession): The active DB session.
            thread_ids (list[int]): The threads to read.

        Returns:
            dict[int, list[EmailMessageEntity]]: One entry per requested id,
                empty for a thread with no messages, ordered as
                ``list_by_thread`` orders them. Empty, without a query, for no
                ids.
        """
        if not thread_ids:
            return {}
        result = await session.execute(
            select(EmailMessageEntity)
            .options(
                defer(EmailMessageEntity.body_html, raiseload=True),
                defer(EmailMessageEntity.body_text, raiseload=True),
            )
            .where(EmailMessageEntity.thread_id.in_(thread_ids))
            .order_by(
                func.coalesce(
                    EmailMessageEntity.gmail_internal_date,
                    EmailMessageEntity.created_at,
                ).asc(),
                EmailMessageEntity.message_id.asc(),
            )
        )
        by_thread: dict[int, list[EmailMessageEntity]] = {i: [] for i in thread_ids}
        for message in result.scalars().all():
            by_thread[message.thread_id].append(message)
        return by_thread
