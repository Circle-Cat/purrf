"""Writes a notification row, then emails it once the transaction commits.

Two phases, because the order matters in both directions. The row has to be
written inside the caller's transaction so it is atomic with the event that
caused it -- an assignment that rolls back must not leave a notification
behind. The email has to be sent *after* that transaction commits, or a
rollback would leave a recipient holding a message about an assignment that
never happened.

Buffering lives on ``session.info``, so it is scoped to the request's
session rather than to this (single, shared) service instance.
"""

import asyncio

from backend.recruiting import notification_email_copy

_BUFFER_KEY = "pending_notification_emails"


class NotificationDispatcher:
    """Records in-app notifications and emails them after commit."""

    def __init__(
        self,
        notification_repository,
        notification_service,
        user_emails_repository,
        email_service,
        logger,
    ):
        """
        Args:
            notification_repository (NotificationRepository): Row insert.
            notification_service (RecruitingNotificationService): Resolves a
                row into its display DTO plus the application's stage.
            user_emails_repository (UserEmailsRepository): Recipient
                addresses.
            email_service (NotificationEmailService): Send transport.
            logger (Logger): Where skipped and failed sends go.
        """
        self._notification_repository = notification_repository
        self._notification_service = notification_service
        self._user_emails_repository = user_emails_repository
        self._email_service = email_service
        self._logger = logger

    async def record(self, session, entity):
        """Insert a notification row and queue it for email on flush.

        Args:
            session (AsyncSession): The caller's session, still in its
                transaction.
            entity (NotificationEntity): The notification to write.

        Returns:
            NotificationEntity: The inserted row, id populated.
        """
        row = await self._notification_repository.create(session, entity)
        session.info.setdefault(_BUFFER_KEY, []).append(row)
        return row

    async def flush(self, session):
        """Email every notification recorded since the last flush.

        Call this *after* ``session.commit()``. Best-effort throughout: one
        recipient without an address, one row that fails to render, or one
        rejected send must not stop the others, and nothing here may raise
        into the caller -- the business action has already succeeded.

        Args:
            session (AsyncSession): The caller's session, post-commit.
        """
        rows = session.info.pop(_BUFFER_KEY, [])
        if not rows:
            return
        addresses = await self._user_emails_repository.get_contact_emails_by_user_ids(
            session, [row.user_id for row in rows]
        )
        sends = []
        for row in rows:
            address = addresses.get(row.user_id)
            if not address:
                self._logger.warning(
                    "No email address for user %s; notification %s delivered "
                    "in-app only",
                    row.user_id,
                    row.type,
                )
                continue
            try:
                dto, stage = await self._notification_service.resolve(session, row)
                subject, body = notification_email_copy.render(dto, stage)
            except Exception:
                self._logger.error(
                    "Failed to render notification %s for user %s",
                    row.type,
                    row.user_id,
                    exc_info=True,
                )
                continue
            sends.append(self._email_service.send(address, subject, body))
        # gather so a mention of three people, or a posting with three
        # owners, costs one round trip's latency rather than three.
        # NotificationEmailService.send already swallows its own failures;
        # return_exceptions is belt-and-braces so an unexpected one here
        # still cannot surface to the caller.
        if sends:
            await asyncio.gather(*sends, return_exceptions=True)
