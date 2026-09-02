from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.entity.training_retired_prefix_entity import TrainingRetiredPrefixEntity


class TrainingRetiredPrefixRepository:
    """Prefixes waiting for the delayed cleanup."""

    async def add(
        self,
        session: AsyncSession,
        course_id: int,
        storage_prefix: str,
        delete_after: datetime,
    ) -> TrainingRetiredPrefixEntity:
        """Record a prefix that a newer upload replaced."""
        row = TrainingRetiredPrefixEntity(
            course_id=course_id,
            storage_prefix=storage_prefix,
            delete_after=delete_after,
        )
        session.add(row)
        await session.flush()
        return row

    async def due(
        self, session: AsyncSession, now: datetime
    ) -> list[TrainingRetiredPrefixEntity]:
        """Prefixes whose delay has elapsed and that are still undeleted."""
        result = await session.execute(
            select(TrainingRetiredPrefixEntity).where(
                TrainingRetiredPrefixEntity.deleted_at.is_(None),
                TrainingRetiredPrefixEntity.delete_after <= now,
            )
        )
        return list(result.scalars().all())
