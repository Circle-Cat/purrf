from datetime import date

from backend.common.recruiting_enums import ApplicationStage
from backend.entity.application_entity import ApplicationEntity
from backend.entity.job_entity import JobEntity
from backend.entity.users_entity import UsersEntity
from sqlalchemy import Date, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession


class ApplicationRepository:
    """Database operations for ApplicationEntity (one row per job+user)."""

    async def list_by_job(
        self, session: AsyncSession, job_id: int
    ) -> list[tuple[ApplicationEntity, UsersEntity]]:
        """Return every application for a job, joined with its applicant.

        Args:
            session (AsyncSession): The active DB session.
            job_id (int): The job whose applications to list.

        Returns:
            list[tuple[ApplicationEntity, UsersEntity]]: (application, user)
                pairs ordered by application_id (stable board card order).
        """
        result = await session.execute(
            select(ApplicationEntity, UsersEntity)
            .join(UsersEntity, ApplicationEntity.user_id == UsersEntity.user_id)
            .where(ApplicationEntity.job_id == job_id)
            .order_by(ApplicationEntity.application_id)
        )
        return [tuple(row) for row in result.all()]

    async def list_by_user(
        self, session: AsyncSession, user_id: int
    ) -> list[tuple[ApplicationEntity, JobEntity]]:
        """Return every application a candidate has ever submitted, joined
        with its job, for the cross-posting aggregation view.

        Args:
            session (AsyncSession): The active DB session.
            user_id (int): The candidate whose applications to list.

        Returns:
            list[tuple[ApplicationEntity, JobEntity]]: (application, job)
                pairs ordered by application_id, across every job the
                candidate has applied to.
        """
        result = await session.execute(
            select(ApplicationEntity, JobEntity)
            .join(JobEntity, ApplicationEntity.job_id == JobEntity.job_id)
            .where(ApplicationEntity.user_id == user_id)
            .order_by(ApplicationEntity.application_id)
        )
        return [tuple(row) for row in result.all()]

    async def count_by_job_and_stage(
        self,
        session: AsyncSession,
        start_date: date,
        end_date: date,
        job_ids: list[int] | None,
    ) -> list[tuple[int, ApplicationStage, int]]:
        """Application counts grouped by job and current stage, for the
        recruiting audit page's stage-breakdown chart/table.

        Args:
            session (AsyncSession): The active DB session.
            start_date (date): Inclusive lower bound on the calendar date
                portion of ``created_datetime``.
            end_date (date): Inclusive upper bound on the calendar date
                portion of ``created_datetime``.
            job_ids (list[int] | None): Restrict to these jobs; None or an
                empty list means every job.

        Returns:
            list[tuple[int, ApplicationStage, int]]: (job_id, stage, count)
                rows, one per (job, stage) combination with at least one
                matching application. Terminal stages (HIRED/REJECTED/
                OFFER_DECLINED/BLACKLISTED) are included alongside the
                configurable pipeline stages.
        """
        created_date = cast(ApplicationEntity.created_datetime, Date)
        stmt = (
            select(
                ApplicationEntity.job_id,
                ApplicationEntity.stage,
                func.count().label("count"),
            )
            .where(created_date >= start_date, created_date <= end_date)
            .group_by(ApplicationEntity.job_id, ApplicationEntity.stage)
        )
        if job_ids:
            stmt = stmt.where(ApplicationEntity.job_id.in_(job_ids))
        result = await session.execute(stmt)
        return [(row.job_id, row.stage, row.count) for row in result.all()]

    async def count_by_job_and_day(
        self,
        session: AsyncSession,
        start_date: date,
        end_date: date,
        job_ids: list[int] | None,
    ) -> list[tuple[int, date, int]]:
        """Application counts grouped by job and submission day, for the
        recruiting audit page's daily trend line chart.

        Args:
            session (AsyncSession): The active DB session.
            start_date (date): Inclusive lower bound on the calendar date
                portion of ``created_datetime``.
            end_date (date): Inclusive upper bound on the calendar date
                portion of ``created_datetime``.
            job_ids (list[int] | None): Restrict to these jobs; None or an
                empty list means every job.

        Returns:
            list[tuple[int, date, int]]: (job_id, day, count) rows, one
                per (job, day) combination with at least one matching
                application.
        """
        created_date = cast(ApplicationEntity.created_datetime, Date)
        stmt = (
            select(
                ApplicationEntity.job_id,
                created_date.label("day"),
                func.count().label("count"),
            )
            .where(created_date >= start_date, created_date <= end_date)
            .group_by(ApplicationEntity.job_id, created_date)
        )
        if job_ids:
            stmt = stmt.where(ApplicationEntity.job_id.in_(job_ids))
        result = await session.execute(stmt)
        return [(row.job_id, row.day, row.count) for row in result.all()]

    async def get_by_job_and_user(
        self, session: AsyncSession, job_id: int, user_id: int
    ) -> ApplicationEntity | None:
        """Return the application for this job+user, or None."""
        result = await session.execute(
            select(ApplicationEntity).where(
                ApplicationEntity.job_id == job_id,
                ApplicationEntity.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_id(
        self,
        session: AsyncSession,
        application_id: int,
        *,
        for_update: bool = False,
    ) -> ApplicationEntity | None:
        """Return the application with this application_id, or None.

        When ``for_update`` is True the row is selected ``FOR UPDATE`` so a
        concurrent stage/sub-status decision on the same application blocks
        until this transaction commits (mirrors
        ``JobReviewRepository.get``'s row lock).
        """
        stmt = select(ApplicationEntity).where(
            ApplicationEntity.application_id == application_id,
        )
        if for_update:
            stmt = stmt.with_for_update()
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(
        self, session: AsyncSession, entity: ApplicationEntity
    ) -> ApplicationEntity:
        """Insert an application and flush so its application_id is populated."""
        session.add(entity)
        await session.flush()
        return entity

    async def update(
        self, session: AsyncSession, entity: ApplicationEntity
    ) -> ApplicationEntity:
        """Persist mutations to an application entity."""
        merged = await session.merge(entity)
        await session.flush()
        return merged
