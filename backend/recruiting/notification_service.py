from sqlalchemy.ext.asyncio import AsyncSession

from backend.dto.notification_dto import (
    NotificationDto,
    NotificationListDto,
    UnreadCountDto,
)


class RecruitingNotificationService:
    """Read-side logic for in-app notifications: list + dismiss/dismiss-all.

    Notifications are light reminders: dismissing one (the frontend's
    "read") deletes the row outright, so everything listed is pending.

    The write side (creating notifications) is deliberately NOT here --
    BoardService/ApplicationService/JobService call
    NotificationRepository.create(...) directly at each trigger point, in
    the same transaction as the event that caused it. See the
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

    async def _display_name(self, session: AsyncSession, user_id: int | None) -> str:
        """Resolve a user id to "First Last", or "" if missing/None."""
        if user_id is None:
            return ""
        user = await self.users_repository.get_user_by_user_id(session, user_id)
        return f"{user.first_name} {user.last_name}".strip() if user is not None else ""

    async def _to_dto(self, session: AsyncSession, row) -> NotificationDto:
        """Resolve one NotificationEntity's display fields into a NotificationDto."""
        job_title = ""
        applicant_name = ""
        job_id = row.job_id
        if row.application_id is not None:
            application = await self.application_repository.get_by_id(
                session, row.application_id
            )
            if application is not None:
                job_id = application.job_id
                job = await self.job_repository.get_by_job_id(
                    session, application.job_id
                )
                job_title = job.title if job is not None else ""
                applicant_name = await self._display_name(session, application.user_id)
        elif row.job_id is not None:
            job = await self.job_repository.get_by_job_id(session, row.job_id)
            job_title = job.title if job is not None else ""

        actor_name = (
            await self._display_name(session, row.actor_user_id)
            if row.actor_user_id is not None
            else None
        )

        return NotificationDto(
            id=row.notification_id,
            type=row.type,
            application_id=row.application_id,
            job_id=job_id,
            round=row.round,
            job_title=job_title,
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
        """Delete one notification (no-op if it isn't user_id's) and commit.

        Args:
            session (AsyncSession): Active database async session.
            user_id (int): The authenticated caller.
            notification_id (int): The notification to dismiss.

        Returns:
            UnreadCountDto: The caller's pending count after the delete.
        """
        await self.notification_repository.delete_by_id(
            session, notification_id, user_id
        )
        await session.commit()
        unread_count = await self.notification_repository.count_by_user(
            session, user_id
        )
        return UnreadCountDto(unread_count=unread_count)

    async def dismiss_all(self, session: AsyncSession, user_id: int) -> UnreadCountDto:
        """Delete every one of user_id's notifications and commit.

        Args:
            session (AsyncSession): Active database async session.
            user_id (int): The authenticated caller.

        Returns:
            UnreadCountDto: Always unread_count=0.
        """
        await self.notification_repository.delete_all_by_user(session, user_id)
        await session.commit()
        unread_count = await self.notification_repository.count_by_user(
            session, user_id
        )
        return UnreadCountDto(unread_count=unread_count)
