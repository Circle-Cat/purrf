from datetime import date, datetime

from backend.common.communication_enums import ContextType
from backend.common.mentorship_enums import ParticipantRole
from backend.common.recruiting_enums import ApplicationStage, JobKind
from backend.entity.application_entity import ApplicationEntity
from backend.entity.email_thread_entity import EmailThreadEntity
from backend.entity.job_entity import JobEntity
from backend.entity.user_emails_entity import UserEmailsEntity
from backend.entity.users_entity import UsersEntity
from sqlalchemy import Date, and_, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession


class ApplicationRepository:
    """Database operations for ApplicationEntity.

    Rejected attempts accumulate as history rows, so this is no longer one
    row per job+user: a job+user pair may have any number of REJECTED rows
    plus at most one non-rejected (live) row.
    """

    async def list_by_job(
        self,
        session: AsyncSession,
        job_id: int,
        exclude_stages: set[ApplicationStage] | None = None,
    ) -> list[tuple[ApplicationEntity, UsersEntity]]:
        """Return each user's latest application for a job, joined with its
        applicant, ordered by application_id (stable board card order).

        Each user's latest attempt only — prior rejected attempts are
        history, surfaced on the application detail page instead of the
        board.

        Args:
            session (AsyncSession): The active DB session.
            job_id (int): The job whose applications to list.
            exclude_stages: if given, latest rows in these stages are dropped
                (the board loads active stages here and paginates terminal
                stages separately).

        Returns:
            list[tuple[ApplicationEntity, UsersEntity]]: (application, user)
                pairs ordered by application_id (stable board card order).
        """
        latest_ids = (
            select(func.max(ApplicationEntity.application_id))
            .where(ApplicationEntity.job_id == job_id)
            .group_by(ApplicationEntity.user_id)
        )
        stmt = (
            select(ApplicationEntity, UsersEntity)
            .join(UsersEntity, ApplicationEntity.user_id == UsersEntity.user_id)
            .where(
                ApplicationEntity.job_id == job_id,
                ApplicationEntity.application_id.in_(latest_ids),
            )
        )
        if exclude_stages:
            stmt = stmt.where(ApplicationEntity.stage.notin_(exclude_stages))
        stmt = stmt.order_by(ApplicationEntity.application_id)
        result = await session.execute(stmt)
        return [tuple(row) for row in result.all()]

    async def list_by_job_and_stage(
        self,
        session: AsyncSession,
        job_id: int,
        stage: ApplicationStage,
        limit: int,
        offset: int,
    ) -> list[tuple[ApplicationEntity, UsersEntity]]:
        """One page of a single stage's latest-per-user applications,
        newest-entry first. The stage filter is applied to the LATEST row
        (outer query), so a user who re-applied does not surface an old
        rejected attempt here.

        Args:
            session (AsyncSession): The active DB session.
            job_id (int): The job whose applications to list.
            stage (ApplicationStage): The terminal (or any) stage to page.
            limit (int): Max rows to return.
            offset (int): Rows to skip, for paging.

        Returns:
            list[tuple[ApplicationEntity, UsersEntity]]: (application, user)
                pairs ordered by stage_entered_at desc, application_id desc.
        """
        latest_ids = (
            select(func.max(ApplicationEntity.application_id))
            .where(ApplicationEntity.job_id == job_id)
            .group_by(ApplicationEntity.user_id)
        )
        result = await session.execute(
            select(ApplicationEntity, UsersEntity)
            .join(UsersEntity, ApplicationEntity.user_id == UsersEntity.user_id)
            .where(
                ApplicationEntity.job_id == job_id,
                ApplicationEntity.stage == stage,
                ApplicationEntity.application_id.in_(latest_ids),
            )
            .order_by(
                ApplicationEntity.stage_entered_at.desc(),
                ApplicationEntity.application_id.desc(),
            )
            .limit(limit)
            .offset(offset)
        )
        return [tuple(row) for row in result.all()]

    async def search_latest_by_jobs(
        self,
        session: AsyncSession,
        job_ids: list[int],
        term: str,
        limit: int,
    ) -> list[tuple[ApplicationEntity, UsersEntity]]:
        """Search several jobs' latest-per-(job, user) applications by
        applicant name or any of the applicant's email addresses.

        Latest-per-(job, user) mirrors ``list_by_job``, so every hit
        corresponds to a card the board can actually show — an older rejected
        attempt is history on the detail page and never surfaces here.

        The email predicate is an EXISTS subquery, not a join: a user may
        hold several rows in ``user_emails``, and a join would multiply the
        result rows. It deliberately matches addresses the board never
        DISPLAYS — a card shows only the contact address picked by
        ``UserEmailsRepository.get_contact_emails_by_user_ids`` — because a
        searcher cannot know which of someone's addresses is primary. It also
        does not filter on ``otp_confirmed``: the display path doesn't
        either, and a search narrower than the display would leave visible
        addresses unsearchable.

        Args:
            session (AsyncSession): The active DB session.
            job_ids (list[int]): Jobs to search within. Empty returns [] with
                no query.
            term (str): Case-insensitive substring. SQL wildcards inside it
                are escaped, so a literal ``%`` or ``_`` matches itself.
            limit (int): Max rows to return.

        Returns:
            list[tuple[ApplicationEntity, UsersEntity]]: (application, user)
                pairs ordered by created_datetime desc, application_id desc.
        """
        if not job_ids:
            return []
        latest_ids = (
            select(func.max(ApplicationEntity.application_id))
            .where(ApplicationEntity.job_id.in_(job_ids))
            .group_by(ApplicationEntity.job_id, ApplicationEntity.user_id)
        )
        pattern = term.lower()
        full_name = func.lower(UsersEntity.first_name + " " + UsersEntity.last_name)
        email_match = (
            select(UserEmailsEntity.email_id)
            .where(
                UserEmailsEntity.user_id == UsersEntity.user_id,
                func.lower(UserEmailsEntity.email).contains(pattern, autoescape=True),
            )
            .exists()
        )
        result = await session.execute(
            select(ApplicationEntity, UsersEntity)
            .join(UsersEntity, ApplicationEntity.user_id == UsersEntity.user_id)
            .where(
                ApplicationEntity.job_id.in_(job_ids),
                ApplicationEntity.application_id.in_(latest_ids),
                or_(full_name.contains(pattern, autoescape=True), email_match),
            )
            .order_by(
                ApplicationEntity.created_datetime.desc(),
                ApplicationEntity.application_id.desc(),
            )
            .limit(limit)
        )
        return [tuple(row) for row in result.all()]

    async def count_latest_by_job_and_stage(
        self, session: AsyncSession, job_id: int, stage: ApplicationStage
    ) -> int:
        """Count latest-per-user applications for a job in one stage. Uses the
        SAME outer stage filter as list_by_job_and_stage so total == items.

        NOTE: deliberately named apart from the pre-existing
        count_by_job_and_stage (audit page; GROUP BY stage, no
        latest-per-user semantics).

        Args:
            session (AsyncSession): The active DB session.
            job_id (int): The job whose applications to count.
            stage (ApplicationStage): The terminal (or any) stage to count.

        Returns:
            int: Number of latest-per-user rows in this stage for this job.
        """
        latest_ids = (
            select(func.max(ApplicationEntity.application_id))
            .where(ApplicationEntity.job_id == job_id)
            .group_by(ApplicationEntity.user_id)
        )
        result = await session.execute(
            select(func.count())
            .select_from(ApplicationEntity)
            .where(
                ApplicationEntity.job_id == job_id,
                ApplicationEntity.stage == stage,
                ApplicationEntity.application_id.in_(latest_ids),
            )
        )
        return int(result.scalar_one())

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
                BLACKLISTED) are included alongside the configurable
                pipeline stages.
        """
        created_date = cast(
            func.timezone("UTC", ApplicationEntity.created_datetime), Date
        )
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
        created_date = cast(
            func.timezone("UTC", ApplicationEntity.created_datetime), Date
        )
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

    async def get_latest_by_job_and_user(
        self, session: AsyncSession, job_id: int, user_id: int
    ) -> ApplicationEntity | None:
        """Return the user's LATEST application attempt for this job, or None.

        Rejected attempts accumulate as history rows; the newest row (highest
        application_id) is the live/most-recent attempt.

        Args:
            session (AsyncSession): The active DB session.
            job_id (int): The job to look up.
            user_id (int): The applicant to look up.

        Returns:
            ApplicationEntity | None: The newest application row for this
                job+user, or None if the user never applied.
        """
        result = await session.execute(
            select(ApplicationEntity)
            .where(
                ApplicationEntity.job_id == job_id,
                ApplicationEntity.user_id == user_id,
            )
            .order_by(ApplicationEntity.application_id.desc())
            .limit(1)
        )
        return result.scalars().first()

    async def get_hired_activity_application(
        self, session: AsyncSession, user_id: int, mentorship_role: ParticipantRole
    ) -> ApplicationEntity | None:
        """Return the user's HIRED application for an ACTIVITY posting with
        this mentorship_role, or None.

        Used by the mentorship round-registration gate: a user may only
        register for a round once they have an approved (HIRED) application
        for the matching mentor/mentee activity posting.
        """
        result = await session.execute(
            select(ApplicationEntity)
            .join(JobEntity, ApplicationEntity.job_id == JobEntity.job_id)
            .where(
                ApplicationEntity.user_id == user_id,
                ApplicationEntity.stage == ApplicationStage.HIRED,
                JobEntity.kind == JobKind.ACTIVITY,
                JobEntity.mentorship_role == mentorship_role,
            )
        )
        return result.scalars().first()

    async def get_recent_hired_activity_role(
        self, session: AsyncSession, user_id: int
    ) -> ParticipantRole | None:
        """Return the mentorship role of the user's most recent HIRED
        ACTIVITY application, or None when they have none.

        Source of truth for a user's participant role in a round: the role
        is taken from the activity application they were hired into, not
        from any prior round-participation record. When a user has been
        hired into more than one role-bearing activity posting (e.g. both a
        mentor and a mentee posting), the one they were hired into most
        recently wins. (Future: allow a user to register under multiple
        roles.)

        Ordered by ``stage_entered_at``, which on a HIRED row is the moment
        of that hire, not by application_id: the order someone applied in
        need not be the order they were admitted in, and it is the later
        admission that says what they are now. application_id breaks ties,
        which only arise between two rows predating the stage_entered_at
        column — those were backfilled to a single migration-time value.
        """
        result = await session.execute(
            select(JobEntity.mentorship_role)
            .join(ApplicationEntity, ApplicationEntity.job_id == JobEntity.job_id)
            .where(
                ApplicationEntity.user_id == user_id,
                ApplicationEntity.stage == ApplicationStage.HIRED,
                JobEntity.kind == JobKind.ACTIVITY,
                JobEntity.mentorship_role.is_not(None),
            )
            .order_by(
                ApplicationEntity.stage_entered_at.desc(),
                ApplicationEntity.application_id.desc(),
            )
            .limit(1)
        )
        return result.scalars().first()

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

    async def list_due_email_sync_applications(
        self,
        session: AsyncSession,
        terminal_cutoff: datetime,
        gmail_thread_ids: set[str] | None = None,
    ) -> list[ApplicationEntity]:
        """Applications the email sync should touch.

        An application qualifies when it has at least one email thread and is
        either still in play, or reached a terminal stage recently enough that
        a late reply is still worth capturing.

        The join is driven by ``email_thread`` on purpose: only applications
        that have actually exchanged mail appear there, so the sweep never
        walks the whole application table.

        Args:
            session (AsyncSession): The active DB session.
            terminal_cutoff (datetime): Oldest ``stage_entered_at`` still swept
                for a HIRED/REJECTED application (e.g. now minus seven days).
            gmail_thread_ids (set[str] | None): When given, restrict the result
                to applications owning one of these Gmail threads — the nightly
                delta passes the set Gmail flagged as recently active. When
                ``None`` (the weekly reconcile), every eligible application is
                returned. The eligibility rule itself is identical either way,
                deliberately: it lives here once so the two jobs cannot
                disagree about what is worth syncing.

        Returns:
            list[ApplicationEntity]: Distinct applications, oldest id first.
        """
        conditions = [
            or_(
                ApplicationEntity.stage.not_in([
                    ApplicationStage.HIRED,
                    ApplicationStage.REJECTED,
                ]),
                ApplicationEntity.stage_entered_at >= terminal_cutoff,
            )
        ]
        if gmail_thread_ids is not None:
            conditions.append(EmailThreadEntity.gmail_thread_id.in_(gmail_thread_ids))

        result = await session.execute(
            select(ApplicationEntity)
            .join(
                EmailThreadEntity,
                and_(
                    EmailThreadEntity.context_type == ContextType.APPLICATION,
                    EmailThreadEntity.context_id == ApplicationEntity.application_id,
                ),
            )
            .where(*conditions)
            .distinct()
            .order_by(ApplicationEntity.application_id.asc())
        )
        return list(result.scalars().all())
