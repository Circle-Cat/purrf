from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.entity.gmail_sync_state_entity import GmailSyncStateEntity


class GmailSyncStateRepository:
    """Reads and creates the per-mailbox Gmail sync state row.

    Callers mutate the returned entity and flush; there is no update method.
    """

    async def get(
        self, session: AsyncSession, email_address: str
    ) -> GmailSyncStateEntity | None:
        """Fetch the state row for a mailbox.

        Args:
            session: Active database session.
            email_address: The mailbox address.

        Returns:
            The state row, or None if the mailbox has none yet.
        """
        result = await session.execute(
            select(GmailSyncStateEntity).where(
                GmailSyncStateEntity.email_address == email_address
            )
        )
        return result.scalar_one_or_none()

    async def get_for_update(
        self, session: AsyncSession, email_address: str
    ) -> GmailSyncStateEntity | None:
        """Row-lock the state so concurrent pushes for one mailbox run one at a time.

        Args:
            session: Active database session.
            email_address: The mailbox address.

        Returns:
            The locked state row, or None if the mailbox has none yet.
        """
        result = await session.execute(
            select(GmailSyncStateEntity)
            .where(GmailSyncStateEntity.email_address == email_address)
            .with_for_update()
        )
        return result.scalar_one_or_none()

    async def get_single(self, session: AsyncSession) -> GmailSyncStateEntity | None:
        """Fetch the environment's state row without knowing its mailbox.

        For recording a failure that happened before the mailbox address
        could be looked up.

        Args:
            session: Active database session.

        Returns:
            The only state row, or None if there are none or more than one.
        """
        result = await session.execute(select(GmailSyncStateEntity).limit(2))
        rows = result.scalars().all()
        return rows[0] if len(rows) == 1 else None

    async def create(
        self,
        session: AsyncSession,
        email_address: str,
        last_history_id: int | None,
    ) -> GmailSyncStateEntity:
        """Insert the state row for a mailbox.

        Args:
            session: Active database session.
            email_address: The mailbox address.
            last_history_id: Initial history cursor, or None.

        Returns:
            The flushed entity.
        """
        entity = GmailSyncStateEntity(
            email_address=email_address, last_history_id=last_history_id
        )
        session.add(entity)
        await session.flush()
        return entity
