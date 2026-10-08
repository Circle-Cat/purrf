from backend.entity.application_entity import ApplicationEntity
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

    async def get_by_job_ids(
        self, session: AsyncSession, job_ids: list[int]
    ) -> list[JobEntity]:
        """The jobs with these ids, in no particular order.

        Args:
            session (AsyncSession): Active database async session.
            job_ids (list[int]): The jobs wanted.

        Returns:
            list[JobEntity]: The jobs found; empty, without a query, for no ids.
        """
        if not job_ids:
            return []
        result = await session.execute(
            select(JobEntity).where(JobEntity.job_id.in_(job_ids))
        )
        return list(result.scalars().all())

    async def get_by_application_id(
        self, session: AsyncSession, application_id: int
    ) -> JobEntity | None:
        """The job an application was made to, in one read.

        For callers that hold an application id and want something off the
        posting -- its owners live in pipeline_config -- where reading the
        application row first would be two round trips.

        Args:
            session (AsyncSession): The active async database session.
            application_id (int): The application whose job is wanted.

        Returns:
            JobEntity | None: The job, or None when there is no such
                application. An application cannot outlive its job.
        """
        result = await session.execute(
            select(JobEntity)
            .join(ApplicationEntity, ApplicationEntity.job_id == JobEntity.job_id)
            .where(ApplicationEntity.application_id == application_id)
        )
        return result.scalars().one_or_none()

    async def get_by_application_ids(
        self, session: AsyncSession, application_ids: list[int]
    ) -> dict[int, JobEntity]:
        """The job each application was made to, in one read.

        Args:
            session (AsyncSession): The active async database session.
            application_ids (list[int]): The applications whose jobs are wanted.

        Returns:
            dict[int, JobEntity]: Keyed by application id; applications that do
                not exist are absent. Empty, without a query, for no ids.
        """
        if not application_ids:
            return {}
        result = await session.execute(
            select(ApplicationEntity.application_id, JobEntity)
            .join(JobEntity, ApplicationEntity.job_id == JobEntity.job_id)
            .where(ApplicationEntity.application_id.in_(application_ids))
        )
        return {application_id: job for application_id, job in result.all()}

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
