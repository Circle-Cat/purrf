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

from backend.common.communication_enums import ContextType, EmailDirection


class EmailSyncService:
    def __init__(self, email_conversation_service, application_activity_repository):
        """
        Args:
            email_conversation_service (EmailConversationService): Shared,
                domain-agnostic Gmail sync.
            application_activity_repository (ApplicationActivityRepository):
                Timeline event writes.
        """
        self._conversation_service = email_conversation_service
        self._activity_repo = application_activity_repository

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
