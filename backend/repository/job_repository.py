from backend.entity.job_entity import JobEntity
from backend.common.recruiting_enums import (
    PUBLICLY_VISIBLE_JOB_STATUSES,
    JobStatus,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class JobRepository:
    """Database operations for JobEntity (recruiting postings)."""

    async def create_job(self, session: AsyncSession, entity: JobEntity) -> JobEntity:
        """Insert a new job and flush so its job_id is populated."""
        session.add(entity)
        await session.flush()
        return entity

    async def get_by_job_id(
        self, session: AsyncSession, job_id: int
    ) -> JobEntity | None:
        """Return the job with the given id, or None."""
        if not job_id:
            return None
        result = await session.execute(
            select(JobEntity).where(JobEntity.job_id == job_id)
        )
        return result.scalar_one_or_none()

    async def list_published(self, session: AsyncSession) -> list[JobEntity]:
        """Return jobs whose status is exactly PUBLISHED.

        Kept strict for callers asking the literal-status question; the
        candidate-facing browse list wants ``list_publicly_visible`` instead.
        """
        result = await session.execute(
            select(JobEntity).where(JobEntity.status == JobStatus.PUBLISHED)
        )
        return list(result.scalars().all())

    async def list_publicly_visible(self, session: AsyncSession) -> list[JobEntity]:
        """Return every job that is live to candidates.

        Covers ``PUBLICLY_VISIBLE_JOB_STATUSES``, so a posting whose revision
        or close is still under review stays listed -- it is still serving its
        last approved version.
        """
        result = await session.execute(
            select(JobEntity).where(JobEntity.status.in_(PUBLICLY_VISIBLE_JOB_STATUSES))
        )
        return list(result.scalars().all())

    async def list_all(self, session: AsyncSession) -> list[JobEntity]:
        """Return every job regardless of status (for internal review/admin views)."""
        result = await session.execute(select(JobEntity))
        return list(result.scalars().all())

    async def update_job(self, session: AsyncSession, entity: JobEntity) -> JobEntity:
        """Persist mutations to an attached/merged job entity."""
        merged = await session.merge(entity)
        await session.flush()
        return merged

    async def delete_job(self, session: AsyncSession, entity: JobEntity) -> None:
        """Delete a job entity and flush so the deletion is visible within the transaction.

        Args:
            session (AsyncSession): Active database async session.
            entity (JobEntity): The entity to delete.
        """
        await session.delete(entity)
        await session.flush()
