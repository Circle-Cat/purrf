from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from backend.dto.recruiting_audit_dto import (
    RecruitingAuditDailyCountDto,
    RecruitingAuditJobDto,
    RecruitingAuditOverviewDto,
    RecruitingAuditStageCountDto,
)
from backend.common.recruiting_enums import JobStatus


class AuditService:
    """Cross-posting, read-only application audit data for the recruiting
    audit page — the only view in this codebase not scoped to a job's own
    owners."""

    def __init__(self, job_repository, application_repository):
        """
        Args:
            job_repository (JobRepository): Posting data access.
            application_repository (ApplicationRepository): Container data
                access, including the aggregate count queries this service
                uses.
        """
        self.job_repository = job_repository
        self.application_repository = application_repository

    async def get_overview(
        self,
        session: AsyncSession,
        start_date: date,
        end_date: date,
        job_ids: list[int] | None,
    ) -> RecruitingAuditOverviewDto:
        """Cross-posting application audit data for the given filters.

        Args:
            session (AsyncSession): Active database async session.
            start_date (date): Inclusive lower bound on submission date for
                ``stage_breakdown``/``daily_trend``.
            end_date (date): Inclusive upper bound on submission date for
                ``stage_breakdown``/``daily_trend``.
            job_ids (list[int] | None): Restrict ``stage_breakdown``/
                ``daily_trend`` to these jobs; None or an empty list means
                every job. Does not affect ``jobs``/``open_positions_count``,
                which are always computed over every job.

        Returns:
            RecruitingAuditOverviewDto: The full audit page payload.
        """
        jobs = await self.job_repository.list_all(session)
        job_titles = {job.job_id: job.title for job in jobs}
        open_positions_count = sum(
            1 for job in jobs if job.status == JobStatus.PUBLISHED
        )

        filter_ids = job_ids or None
        stage_rows = await self.application_repository.count_by_job_and_stage(
            session, start_date, end_date, filter_ids
        )
        daily_rows = await self.application_repository.count_by_job_and_day(
            session, start_date, end_date, filter_ids
        )

        return RecruitingAuditOverviewDto(
            open_positions_count=open_positions_count,
            jobs=[
                RecruitingAuditJobDto(id=job.job_id, title=job.title, status=job.status)
                for job in jobs
            ],
            stage_breakdown=[
                RecruitingAuditStageCountDto(
                    job_id=job_id,
                    job_title=job_titles.get(job_id, ""),
                    stage=stage,
                    count=count,
                )
                for job_id, stage, count in stage_rows
            ],
            daily_trend=[
                RecruitingAuditDailyCountDto(
                    job_id=job_id,
                    job_title=job_titles.get(job_id, ""),
                    date=day,
                    count=count,
                )
                for job_id, day, count in daily_rows
            ],
        )
