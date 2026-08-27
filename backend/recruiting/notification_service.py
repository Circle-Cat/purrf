from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.name_utils import display_name_of
from backend.entity.event_entity import EventEntity
from backend.dto.notification_dto import (
    NotificationDto,
    NotificationListDto,
    UnreadCountDto,
)


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
        """
        self.notification_repository = notification_repository
        self.application_repository = application_repository
        self.job_repository = job_repository
        self.users_repository = users_repository

    async def _candidate_name(self, session: AsyncSession, user_id: int | None) -> str:
        """Resolve a candidate id to their legal "First Last", or "".

        A candidate is named the way their application names them, so a
        preferred name on their profile does not apply here.
        """
        if user_id is None:
            return ""
        user = await self.users_repository.get_user_by_user_id(session, user_id)
        return f"{user.first_name} {user.last_name}".strip() if user is not None else ""

    async def _actor_name(self, session: AsyncSession, user_id: int | None) -> str:
        """Resolve an acting colleague's id to their display name, or "".

        The actor is internal, so the shared rule applies: preferred name
        first, full name as the fallback.
        """
        if user_id is None:
            return ""
        user = await self.users_repository.get_user_by_user_id(session, user_id)
        return display_name_of(user)

    async def _to_dto(self, session: AsyncSession, row) -> NotificationDto:
        """Resolve one notification row into what the bell renders.

        What happened is read from the event the row points at, not from the
        row: the row is only "user U needs to know about event E". Display
        names are resolved now rather than stored, so a renamed user reads
        correctly on the next open.

        Args:
            session (AsyncSession): Active database async session.
            row (NotificationEntity): The notification to resolve.

        Returns:
            NotificationDto: Empty display fields where the referenced rows
                are gone, and a null actor_name where nobody acted.
        """
        event = await session.get(EventEntity, row.event_id)
        job_title = ""
        job_kind = None
        applicant_name = ""
        if event is not None and event.subject_type == "application":
            application = await self.application_repository.get_by_id(
                session, event.subject_id
            )
            if application is not None:
                job = await self.job_repository.get_by_job_id(
                    session, application.job_id
                )
                job_title = job.title if job is not None else ""
                job_kind = job.kind if job is not None else None
                applicant_name = await self._candidate_name(
                    session, application.user_id
                )
        elif event is not None and event.subject_type == "job":
            job = await self.job_repository.get_by_job_id(session, event.subject_id)
            job_title = job.title if job is not None else ""
            job_kind = job.kind if job is not None else None

        actor_name = (
            await self._actor_name(session, event.actor_id)
            if event is not None and event.actor_id is not None
            else None
        )

        return NotificationDto(
            id=row.notification_id,
            event_type=event.event_type if event is not None else "",
            details=event.details if event is not None else {},
            job_title=job_title,
            job_kind=job_kind,
            applicant_name=applicant_name,
            actor_name=actor_name,
            created_at=row.created_at,
        )

    async def list_for_user(
        self, session: AsyncSession, user_id: int, limit: int = 20, offset: int = 0
    ) -> NotificationListDto:
        """List one user's notifications (newest first) plus their pending count.

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
        items = [await self._to_dto(session, row) for row in rows]
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
