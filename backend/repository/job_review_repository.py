from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.entity.job_review_entity import JobReviewEntity
from backend.common.recruiting_enums import JobReviewStatus


class JobReviewRepository:
    """Database operations for JobReviewEntity (job-posting review cycles)."""

    async def create(
        self, session: AsyncSession, entity: JobReviewEntity
    ) -> JobReviewEntity:
        """Insert a review and flush so its review_id is populated."""
        session.add(entity)
        await session.flush()
        return entity

    async def get(
        self, session: AsyncSession, review_id: int
    ) -> JobReviewEntity | None:
        """Return the review with the given id, or None."""
        if not review_id:
            return None
        result = await session.execute(
            select(JobReviewEntity).where(JobReviewEntity.review_id == review_id)
        )
        return result.scalar_one_or_none()

    async def list_by_reviewer(
        self,
        session: AsyncSession,
        reviewer_id: int,
        statuses: Sequence[JobReviewStatus],
    ) -> list[JobReviewEntity]:
        """Return the reviewer's reviews whose status is in `statuses`."""
        result = await session.execute(
            select(JobReviewEntity).where(
                JobReviewEntity.reviewer_id == reviewer_id,
                JobReviewEntity.status.in_(statuses),
            )
        )
        return list(result.scalars().all())

    async def get_open_for_job(
        self, session: AsyncSession, job_id: int
    ) -> JobReviewEntity | None:
        """Return the job's pending review, or None if there is none open."""
        if not job_id:
            return None
        result = await session.execute(
            select(JobReviewEntity).where(
                JobReviewEntity.job_id == job_id,
                JobReviewEntity.status == JobReviewStatus.PENDING,
            )
        )
        return result.scalar_one_or_none()
