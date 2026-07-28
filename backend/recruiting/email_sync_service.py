"""Recruiting-side email synchronisation.

The shared :class:`~backend.communication.email_conversation_service.EmailConversationService`
knows how to sync one ``(user, context)`` pair and nothing else — no
permissions, no recruiting concepts. This service is the recruiting half: it
decides *which* applications are worth syncing and records the domain
consequence of a sync (an ``email_received`` timeline event per inbound
reply).

Both entry points into a sync go through here — the recruiter pressing
Refresh (via ``board_service``, which adds the owner gate) and the nightly
cron sweep — so the timeline-writing rule lives in exactly one place.
"""

import logging
from datetime import datetime, timedelta, timezone

from backend.common.communication_enums import ContextType, EmailDirection

# A terminal application keeps getting swept for this long, so a reply that
# lands just after a rejection is still captured. Past that it is left to
# manual Refresh, which has no window at all.
_TERMINAL_SYNC_WINDOW = timedelta(days=7)


class EmailSyncService:
    def __init__(
        self,
        email_conversation_service,
        application_activity_repository,
        application_repository,
        logger,
    ):
        """
        Args:
            email_conversation_service (EmailConversationService): Shared,
                domain-agnostic Gmail sync.
            application_activity_repository (ApplicationActivityRepository):
                Timeline event writes.
            application_repository (ApplicationRepository): Supplies the
                nightly sweep's eligibility query.
            logger: Application logger. The sweep's outcome is only visible
                here — see ``sync_due_applications``.
        """
        self._conversation_service = email_conversation_service
        self._activity_repo = application_activity_repository
        self._application_repo = application_repository
        self._logger = logger

    async def sync_application(self, session, application):
        """Sync one application's email threads and log the new inbound replies.

        Writes an ``email_received`` timeline event per newly-persisted INBOUND
        message, backdated to when the mail actually arrived. Outbound messages
        picked up by a sync are deliberately not logged — the send path already
        wrote an ``email_sent`` event when we sent them.

        Does **not** commit: the caller owns the transaction boundary (manual
        Refresh commits once; the nightly sweep commits per application so one
        failure cannot undo its predecessors).

        Args:
            session (AsyncSession): The active DB session.
            application (ApplicationEntity): The application to sync.

        Returns:
            list[EmailMessageEntity]: The messages newly persisted this call.

        Raises:
            RateLimitedError / RuntimeError: Propagated from the Gmail sync.
        """
        new_messages = await self._conversation_service.sync_context(
            session, ContextType.APPLICATION, application.application_id
        )
        for message in new_messages:
            if message.direction != EmailDirection.INBOUND:
                continue
            await self._activity_repo.create(
                session,
                application.application_id,
                application.user_id,
                "email_received",
                details={
                    "subject": message.subject,
                    "from": message.from_address,
                    "to": message.to_addresses,
                    "cc": message.cc_addresses,
                    "threadId": message.thread_id,
                    "direction": "inbound",
                },
                created_at=message.gmail_internal_date,
            )
        return new_messages

    async def sync_due_applications(self, session):
        """Sync every application whose email threads are still worth watching.

        Each application is its own unit of work: synced, then committed, then
        the next one. A failure is caught, logged and counted, and the sweep
        moves on.

        That is deliberately the opposite of ``sync_application``'s own
        behaviour, which propagates. For a recruiter pressing Refresh on one
        application, failing loudly is right — they retry and the retry
        self-heals. For a nightly pass over everything, one rate-limited or
        deleted thread must not cost every later application its sync, with
        nobody watching.

        Committing per application follows from that: a shared transaction
        would let a late failure roll back work that already succeeded.

        Args:
            session (AsyncSession): The active DB session.

        Returns:
            dict: ``{"scanned", "synced", "failed", "newMessages"}``.
        """
        cutoff = datetime.now(timezone.utc) - _TERMINAL_SYNC_WINDOW
        due = await self._application_repo.list_due_email_sync_applications(
            session, cutoff
        )

        synced = 0
        failed = 0
        new_message_count = 0
        for application in due:
            try:
                new_messages = await self.sync_application(session, application)
                await session.commit()
                synced += 1
                new_message_count += len(new_messages)
            except Exception:
                await session.rollback()
                self._logger.exception(
                    "[EmailSync] application_id=%s sync failed",
                    application.application_id,
                )
                failed += 1

        # The endpoint returns 200 even with failures, so the k8s job is always
        # green — this line is the only place the outcome shows up. WARNING
        # when anything failed makes "did tonight go wrong?" greppable.
        self._logger.log(
            logging.WARNING if failed else logging.INFO,
            "[EmailSync] sweep finished: scanned=%d synced=%d failed=%d "
            "new_messages=%d",
            len(due),
            synced,
            failed,
            new_message_count,
        )
        return {
            "scanned": len(due),
            "synced": synced,
            "failed": failed,
            "newMessages": new_message_count,
        }
