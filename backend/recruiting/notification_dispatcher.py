"""Writes a notification row, then nudges the worker that emails it.

Two phases, because the order matters in both directions. The row has to be
written inside the caller's transaction so it is atomic with the event that
caused it -- an assignment that rolls back must not leave a notification
behind. The email has to go out *after* that transaction commits, or a
rollback would leave a recipient holding a message about an assignment that
never happened.

The row itself is the queue: ``email_sent_at IS NULL`` means "not yet
emailed", so a committed notification is a durable instruction to send, and
:class:`NotificationEmailWorker` is the only thing that acts on it. That is
the whole reason this no longer sends inline. Sending inline made the
candidate's submit request wait on Gmail -- measured at 6.0s of an 8.3s
request, none of which fed the response -- and lost the email outright if
the pod died between the commit and the send.

``flush`` therefore no longer flushes anything; it wakes the worker so a
just-committed notification goes out in the next moment rather than at the
worker's next periodic sweep. It is a hint, not a handoff: if the process
dies before the worker acts, the committed row is still there and the next
sweep (or the next pod's startup pass) delivers it.
"""


class NotificationDispatcher:
    """Records in-app notifications and wakes the email worker."""

    def __init__(self, notification_repository, email_worker):
        """
        Args:
            notification_repository (NotificationRepository): Row insert.
            email_worker (NotificationEmailWorker): Told when new rows exist,
                so delivery does not wait for the periodic sweep.
        """
        self._notification_repository = notification_repository
        self._email_worker = email_worker

    async def record(self, session, entity):
        """Insert a notification row inside the caller's transaction.

        Args:
            session (AsyncSession): The caller's session, still in its
                transaction.
            entity (NotificationEntity): The notification to write.

        Returns:
            NotificationEntity: The inserted row, id populated.
        """
        return await self._notification_repository.create(session, entity)

    async def flush(self):
        """Wake the email worker; call this *after* ``session.commit()``.

        Cheap and non-blocking by design: it sets an event and returns, so a
        request path pays no DB round trip and no Gmail call for it. Safe to
        call when nothing was recorded -- the worker finds an empty outbox
        and goes back to sleep.
        """
        self._email_worker.wake()
