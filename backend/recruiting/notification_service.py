from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.name_utils import display_name_of
from backend.common.user_enums import USER_SUBJECT_TYPE
from backend.dto.notification_dto import (
    NotificationDto,
    NotificationListDto,
    UnreadCountDto,
)
from backend.recruiting.candidate_names import candidate_names


async def _by_id(load, session, ids, key):
    """Load the rows with ``ids`` through ``load`` and key them by ``key``.

    No ids means no call at all: a page with no application-scoped rows has
    no reason to touch the applications table.
    """
    if not ids:
        return {}
    return {getattr(row, key): row for row in await load(session, sorted(ids))}


class RecruitingNotificationService:
    """Read-side logic for in-app notifications: list + dismiss/dismiss-all.

    Notifications are light reminders: dismissing one (the frontend's
    "read") marks it, so everything listed is undismissed. The row survives
    because it also carries the email state machine.

    The write side (creating notifications) is deliberately NOT here --
    ``record_event`` writes the event and one row per resolved recipient, in
    the same transaction as the change that caused it. See the
    notification-system design spec for why the two sides aren't merged.
    """

    def __init__(
        self,
        notification_repository,
        application_repository,
        job_repository,
        users_repository,
        event_repository,
        application_submission_repository,
    ):
        """
        Args:
            notification_repository (NotificationRepository): Notification data access.
            application_repository (ApplicationRepository): Resolves an
                application-scoped notification's job/applicant labels.
            job_repository (JobRepository): Resolves job titles for both
                application-scoped and job-review-scoped notifications.
            users_repository (UsersRepository): Resolves applicant/actor
                display names.
            event_repository (EventRepository): Reads the event each
                notification points at, which is what says what happened.
            application_submission_repository (ApplicationSubmissionRepository):
                Reads the name a candidate with a nameless account typed into
                their application.
        """
        self.notification_repository = notification_repository
        self.application_repository = application_repository
        self.job_repository = job_repository
        self.users_repository = users_repository
        self.event_repository = event_repository
        self.application_submission_repository = application_submission_repository

    @staticmethod
    def _to_dto(
        row, events, applications, jobs, users, applicant_names
    ) -> NotificationDto:
        """Resolve one notification row into what the bell renders.

        What happened is read from the event the row points at, not from the
        row: the row is only "user U needs to know about event E". Display
        names are resolved now rather than stored, so a renamed user reads
        correctly on the next open.

        Args:
            row (NotificationEntity): The notification to resolve.
            events (dict[int, EventEntity]): The page's events by id.
            applications (dict[int, ApplicationEntity]): Their applications by id.
            jobs (dict[int, JobEntity]): Their jobs by id.
            users (dict[int, UsersEntity]): Their candidates, actors and
                user subjects by id.
            applicant_names (dict[int, str]): Their candidates' names by user
                id, resolved by the candidate rule rather than the colleague
                one: a preferred name on a candidate's profile does not apply.

        Returns:
            NotificationDto: Empty display fields where the referenced rows
                are gone, and a null actor_name where nobody acted.
        """
        event = events.get(row.event_id)
        job = None
        applicant_name = ""
        subject_name = ""
        if event is not None and event.subject_type == "application":
            application = applications.get(event.subject_id)
            if application is not None:
                job = jobs.get(application.job_id)
                applicant_name = applicant_names.get(application.user_id, "")
        elif event is not None and event.subject_type == USER_SUBJECT_TYPE:
            # A block request is about a person with no application in sight.
            # Named by the colleague rule, which is what the email about the
            # same event uses -- the two channels must agree on who this is.
            subject_name = display_name_of(users.get(event.subject_id))
        elif event is not None and event.subject_type == "job":
            job = jobs.get(event.subject_id)

        actor_name = (
            display_name_of(users.get(event.actor_id))
            if event is not None and event.actor_id is not None
            else None
        )

        return NotificationDto(
            id=row.notification_id,
            event_type=event.event_type if event is not None else "",
            details=event.details if event is not None else {},
            job_title=job.title if job is not None else "",
            job_kind=job.kind if job is not None else None,
            applicant_name=applicant_name,
            subject_name=subject_name,
            actor_name=actor_name,
            created_at=row.created_at,
        )

    async def _load_page(self, session: AsyncSession, rows):
        """Load everything a page of rows refers to, one query per kind.

        Each kind's ids come from the kind before it, so the order is fixed:
        events, then their applications, then the jobs of both, then every
        person named anywhere on the page, then the typed names of the
        candidates among them whose accounts have none.

        Returns:
            tuple[dict, dict, dict, dict, dict]: Events, applications, jobs
                and users, each keyed by id, and the candidates' names keyed
                by user id.
        """
        events = await _by_id(
            self.event_repository.get_by_ids,
            session,
            {row.event_id for row in rows},
            "event_id",
        )
        applications = await _by_id(
            self.application_repository.get_by_ids,
            session,
            {e.subject_id for e in events.values() if e.subject_type == "application"},
            "application_id",
        )
        jobs = await _by_id(
            self.job_repository.get_by_job_ids,
            session,
            {a.job_id for a in applications.values()}
            | {e.subject_id for e in events.values() if e.subject_type == "job"},
            "job_id",
        )
        user_ids = (
            {a.user_id for a in applications.values()}
            | {e.actor_id for e in events.values() if e.actor_id is not None}
            | {
                e.subject_id
                for e in events.values()
                if e.subject_type == USER_SUBJECT_TYPE
            }
        )
        users = await _by_id(
            self.users_repository.get_all_by_ids, session, user_ids, "user_id"
        )
        applicant_names = await candidate_names(
            session,
            self.application_submission_repository,
            [users[a.user_id] for a in applications.values() if a.user_id in users],
        )
        return events, applications, jobs, users, applicant_names

    async def list_for_user(
        self, session: AsyncSession, user_id: int, limit: int = 20, offset: int = 0
    ) -> NotificationListDto:
        """List one user's notifications (newest first) plus their pending count.

        A page costs the same number of queries however many rows it holds:
        see ``_load_page``. The bell refetches on every route change and
        window focus, so a per-row lookup here is paid on every click.

        Args:
            session (AsyncSession): Active database async session.
            user_id (int): The authenticated caller.
            limit (int): Page size.
            offset (int): Page offset.

        Returns:
            NotificationListDto: The page of notifications and the total
                pending count (independent of `limit`/`offset`).
        """
        rows = await self.notification_repository.list_by_user(
            session, user_id, limit, offset
        )
        unread_count = await self.notification_repository.count_by_user(
            session, user_id
        )
        if not rows:
            return NotificationListDto(notifications=[], unread_count=unread_count)
        lookups = await self._load_page(session, rows)
        items = [self._to_dto(row, *lookups) for row in rows]
        return NotificationListDto(notifications=items, unread_count=unread_count)

    async def dismiss(
        self, session: AsyncSession, user_id: int, notification_id: int
    ) -> UnreadCountDto:
        """Mark one notification dismissed (no-op if it isn't user_id's) and commit.

        Args:
            session (AsyncSession): Active database async session.
            user_id (int): The authenticated caller.
            notification_id (int): The notification to dismiss.

        Returns:
            UnreadCountDto: The caller's pending count afterwards.
        """
        await self.notification_repository.dismiss_by_id(
            session, notification_id, user_id
        )
        await session.commit()
        unread_count = await self.notification_repository.count_by_user(
            session, user_id
        )
        return UnreadCountDto(unread_count=unread_count)

    async def dismiss_all(self, session: AsyncSession, user_id: int) -> UnreadCountDto:
        """Mark every one of user_id's notifications dismissed and commit.

        Args:
            session (AsyncSession): Active database async session.
            user_id (int): The authenticated caller.

        Returns:
            UnreadCountDto: Always unread_count=0.
        """
        await self.notification_repository.dismiss_all_by_user(session, user_id)
        await session.commit()
        unread_count = await self.notification_repository.count_by_user(
            session, user_id
        )
        return UnreadCountDto(unread_count=unread_count)
