from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.entity.job_activity_entity import JobActivityEntity


class JobActivityRepository:
    """Database operations for JobActivityEntity (append-only)."""

    async def create(
        self,
        session: AsyncSession,
        job_id: int,
        actor_id: int,
        event_type: str,
        details: dict | None = None,
    ) -> JobActivityEntity:
        """Append one audit entry to a job posting's timeline.

        Args:
            session (AsyncSession): The active DB session.
            job_id (int): The job posting this event happened on.
            actor_id (int): The user who performed the action.
            event_type (str): One of the fixed event-type strings used by
                the callers in ``job_service.py`` (``"job_created"``,
                ``"review_opened"``, ``"review_decided"``).
            details (dict | None): Event-specific payload; defaults to ``{}``.

        Returns:
            JobActivityEntity: The created row.
        """
        entity = JobActivityEntity(
            job_id=job_id,
            actor_id=actor_id,
            event_type=event_type,
            details=details or {},
        )
        session.add(entity)
        await session.flush()
        return entity

    async def list_by_job(
        self, session: AsyncSession, job_id: int
    ) -> list[JobActivityEntity]:
        """Every audit entry for one job posting, newest first.

        Args:
            session (AsyncSession): The active DB session.
            job_id (int): The job posting to fetch history for.

        Returns:
            list[JobActivityEntity]: Ordered by created_at descending,
                falling back to ``activity_id`` descending to break ties.
        """
        result = await session.execute(
            select(JobActivityEntity)
            .where(JobActivityEntity.job_id == job_id)
            .order_by(
                JobActivityEntity.created_at.desc(),
                JobActivityEntity.activity_id.desc(),
            )
        )
        return list(result.scalars().all())
