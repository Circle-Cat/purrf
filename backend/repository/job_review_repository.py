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
        self, session: AsyncSession, review_id: int, *, for_update: bool = False
    ) -> JobReviewEntity | None:
        """Return the review with the given id, or None.

        When ``for_update`` is True the row is selected ``FOR UPDATE`` so a
        concurrent decision on the same review blocks until this transaction
        commits, then re-reads the (now decided) status — serialising deciders.
        """
        if not review_id:
            return None
        stmt = select(JobReviewEntity).where(JobReviewEntity.review_id == review_id)
        if for_update:
            stmt = stmt.with_for_update()
        result = await session.execute(stmt)
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

    async def get_latest_reviews(
        self, session: AsyncSession, job_ids: list[int]
    ) -> dict[int, JobReviewEntity]:
        """Return the most-recent review for each job in job_ids.

        Fetches all reviews whose ``job_id`` is in ``job_ids``, ordered by
        ``created_at`` descending, and keeps only the first-seen entry per
        ``job_id`` (i.e. the newest review).

        Args:
            session (AsyncSession): Active database async session.
            job_ids (list[int]): Posting identifiers to query. An empty list
                short-circuits and returns ``{}`` without hitting the database.

        Returns:
            dict[int, JobReviewEntity]: Maps each job_id that has at least one
            review to that job's most-recent ``JobReviewEntity``. Job ids with
            no reviews are absent from the result.
        """
        if not job_ids:
            return {}
        result = await session.execute(
            select(JobReviewEntity)
            .where(JobReviewEntity.job_id.in_(job_ids))
            .order_by(
                JobReviewEntity.created_at.desc(), JobReviewEntity.review_id.desc()
            )
        )
        rows = result.scalars().all()
        latest: dict[int, JobReviewEntity] = {}
        for row in rows:
            if row.job_id not in latest:
                latest[row.job_id] = row
        return latest
