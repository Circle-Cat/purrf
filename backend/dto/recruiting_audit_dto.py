from datetime import date

from backend.common.recruiting_enums import ApplicationStage, JobKind, JobStatus
from backend.dto.base_dto import BaseDto


class RecruitingAuditJobDto(BaseDto):
    """One posting, for the audit page's job multi-selector. ``kind`` lets
    the page split the stage breakdown into employment/activity sections
    (activity postings have no offer step and label HIRED as Admitted)."""

    id: int
    title: str
    status: JobStatus
    kind: JobKind


class RecruitingAuditStageCountDto(BaseDto):
    """Application count for one (job, stage) pair, for the stage-breakdown
    chart and table."""

    job_id: int
    job_title: str
    stage: ApplicationStage
    count: int


class RecruitingAuditDailyCountDto(BaseDto):
    """New-application count for one (job, day) pair, for the daily trend
    line chart."""

    job_id: int
    job_title: str
    date: date
    count: int


class RecruitingAuditOverviewDto(BaseDto):
    """Full payload for the recruiting audit page.

    ``jobs`` and ``open_positions_count`` are always computed over every
    job regardless of the caller's date-range/job-id filters; only
    ``stage_breakdown``/``daily_trend`` are filtered.
    """

    open_positions_count: int
    jobs: list[RecruitingAuditJobDto]
    stage_breakdown: list[RecruitingAuditStageCountDto]
    daily_trend: list[RecruitingAuditDailyCountDto]
