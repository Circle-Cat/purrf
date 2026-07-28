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

        Thin wrapper over ``_sync_by_ids``: reads the two fields it needs off
        the entity up front and delegates. This is the entry point
        ``board_service.get_application_conversation`` calls with a live
        ``ApplicationEntity`` — that call site depends on this signature and
        must not change.

        Args:
            session (AsyncSession): The active DB session.
            application (ApplicationEntity): The application to sync.

        Returns:
            list[EmailMessageEntity]: The messages newly persisted this call.

        Raises:
            RateLimitedError / RuntimeError: Propagated from the Gmail sync.
        """
        return await self._sync_by_ids(
            session, application.application_id, application.user_id
        )

    async def _sync_by_ids(self, session, application_id, user_id):
        """Sync one application's email threads and log the new inbound replies.

        Writes an ``email_received`` timeline event per newly-persisted INBOUND
        message, backdated to when the mail actually arrived. Outbound messages
        picked up by a sync are deliberately not logged — the send path already
        wrote an ``email_sent`` event when we sent them.

        Does **not** commit: the caller owns the transaction boundary (manual
        Refresh commits once; the nightly sweep commits per application so one
        failure cannot undo its predecessors).

        Takes plain ids rather than an ``ApplicationEntity`` on purpose: this
        must not touch ORM-loaded state, so it stays safe to call after a
        sibling application's ``session.rollback()`` has expired the whole
        identity map (see ``sync_due_applications``).

        Args:
            session (AsyncSession): The active DB session.
            application_id: The application's id.
            user_id: The application owner's user id (the timeline actor).

        Returns:
            list[EmailMessageEntity]: The messages newly persisted this call.

        Raises:
            RateLimitedError / RuntimeError: Propagated from the Gmail sync.
        """
        new_messages = await self._conversation_service.sync_context(
            session, ContextType.APPLICATION, application_id
        )
        for message in new_messages:
            if message.direction != EmailDirection.INBOUND:
                continue
            await self._activity_repo.create(
                session,
                application_id,
                user_id,
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

        # Snapshot the two fields the loop needs as plain values *before* the
        # loop runs. session.rollback() (below, on a failure) expires every
        # ORM object in the identity map, including every other entity in
        # `due` and the one currently being handled — so reading them off the
        # entities inside the loop (e.g. in the except block, after a
        # rollback) can trigger an implicit refresh SELECT. That SELECT runs
        # outside greenlet_spawn and raises sqlalchemy.exc.MissingGreenlet
        # from inside the except block, uncaught, killing the whole sweep on
        # the first failure — exactly what per-application isolation exists
        # to prevent. Do not "simplify" this back to iterating `due` directly.
        targets = [(a.application_id, a.user_id) for a in due]

        synced = 0
        failed = 0
        new_message_count = 0
        for application_id, user_id in targets:
            try:
                new_messages = await self._sync_by_ids(session, application_id, user_id)
                await session.commit()
                synced += 1
                new_message_count += len(new_messages)
            except Exception:
                await session.rollback()
                self._logger.exception(
                    "[EmailSync] application_id=%s sync failed",
                    application_id,
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
