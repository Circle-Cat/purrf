"""Sends one system notification email. Domain-agnostic.

Notification mail is not correspondence: it starts no thread, expects no
reply, and is deliberately not persisted -- unlike
:class:`EmailConversationService`, which files every send into an
``email_thread``/``email_message`` pair bound to a candidate's context. A
notification stored that way would surface as candidate correspondence in
the Emails tab.

Sending is best-effort by design. The in-app notification row is written
and committed before this is ever called, so a failed email costs the
recipient a push, not the notification itself -- which is why a failure is
logged and swallowed rather than raised.
"""

import asyncio


class NotificationEmailService:
    """Delivers a rendered notification email through Gmail."""

    def __init__(self, gmail_client, logger, sender_address):
        """
        Args:
            gmail_client (GmailClient): Send transport. Must already own
                ``sender_address`` -- it refuses an unowned sender, which is
                the guard against Gmail silently rewriting an unregistered
                From to the mailbox owner and reporting success.
            logger (Logger): Where a swallowed send failure goes.
            sender_address (str): The notification From address for this
                environment.
        """
        self._gmail = gmail_client
        self._logger = logger
        self._sender_address = sender_address

    @property
    def sender_address(self):
        """The address this service sends notifications as (so callers/tests
        can verify which Send-As identity was wired in, independent of
        ``GmailClient.owns_address`` -- which cannot distinguish this address
        from any other address the same client owns)."""
        return self._sender_address

    async def send(self, to: str, subject: str, body_html: str) -> bool:
        """Send one notification email, swallowing any failure.

        Args:
            to (str): Single recipient address.
            subject (str): Subject line.
            body_html (str): Rendered HTML body.

        Returns:
            bool: True when Gmail accepted the message, False when the send
            failed (the failure is logged, never raised -- the caller runs
            after the business transaction has already committed and must
            not be able to fail because of mail).
        """
        try:
            await asyncio.to_thread(
                self._gmail.send_message,
                to=[to],
                cc=[],
                subject=subject,
                body=body_html,
                sender=f"Purrf Notifications <{self._sender_address}>",
            )
            return True
        except Exception:
            self._logger.error(
                "Failed to send notification email to %s (subject %r)",
                to,
                subject,
                exc_info=True,
            )
            return False
