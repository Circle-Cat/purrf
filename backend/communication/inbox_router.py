"""Claims a new Gmail thread for the Inbox by the alias its first inbound mail was sent to.

One mailbox serves every environment: each environment claims its own Send-As
aliases. Mail to one of ours becomes an unassigned Inbox thread; mail to
another environment's alias is left for that environment; mail to no Send-As
alias at all is reported as unrouted so ops can look at it.
"""

import asyncio
from dataclasses import dataclass

from sqlalchemy.exc import IntegrityError

from backend.common.communication_enums import INBOX_CONTEXT
from backend.entity.email_thread_entity import EmailThreadEntity


@dataclass(frozen=True)
class RouteResult:
    thread: EmailThreadEntity | None
    unrouted: bool  # True only when the mail hit no Send-As alias at all


def _sent_at(message):
    return int(message.get("gmail_internal_date") or 0)


class InboxRouter:
    def __init__(self, gmail_client, thread_repository, aliases, logger):
        """
        Args:
            gmail_client (GmailClient): Synchronous transport, called off the event loop.
            thread_repository (EmailThreadRepository): Creates and re-reads threads.
            aliases (InboxAliases): The aliases this environment claims.
            logger: Application logger.
        """
        self._gmail = gmail_client
        self._threads = thread_repository
        self._aliases = aliases
        self._logger = logger

    async def route(self, session, gmail_thread_id, mailbox_address):
        """Create the Inbox thread for an untracked Gmail thread, if it is ours.

        Does not commit. The thread is created in a savepoint; when another
        push created it first, that row is returned instead.

        Args:
            session (AsyncSession): The active DB session.
            gmail_thread_id (str): The untracked Gmail thread.
            mailbox_address (str): The mailbox's primary address. Every
                message's Delivered-To names it, so it never counts as an alias.

        Returns:
            RouteResult: The thread (created or re-read), or None with
            ``unrouted`` set when the mail matched no Send-As alias.

        Raises:
            GmailNotFoundError, RateLimitedError, RuntimeError: From Gmail.
        """
        message_ids = await asyncio.to_thread(
            self._gmail.list_thread_message_ids, gmail_thread_id
        )
        messages = (
            await asyncio.to_thread(self._gmail.get_messages, message_ids)
            if message_ids
            else []
        )
        inbound = [
            m for m in messages if not self._gmail.owns_address(m.get("from_address"))
        ]
        if not inbound:
            return RouteResult(thread=None, unrouted=False)

        first = min(inbound, key=_sent_at)
        recipients = first.get("recipients") or []
        service = self._aliases.service_for(recipients)
        if service is None:
            send_as = await asyncio.to_thread(self._gmail.list_send_as_addresses)
            others = set(send_as) - {mailbox_address.lower()}
            hit = [r for r in recipients if r.lower() in others]
            if hit:
                self._logger.info(
                    "[InboxRouter] Gmail thread %s is for %s, a Send-As alias "
                    "this environment does not claim; skipped",
                    gmail_thread_id,
                    hit[0],
                )
                return RouteResult(thread=None, unrouted=False)
            self._logger.warning(
                "[InboxRouter] Gmail thread %s from %s was addressed to no "
                "Send-As alias; it stays in Gmail only",
                gmail_thread_id,
                first.get("from_address"),
            )
            return RouteResult(thread=None, unrouted=True)

        try:
            async with session.begin_nested():
                thread = await self._threads.create(
                    session,
                    user_id=None,
                    gmail_thread_id=gmail_thread_id,
                    subject=first.get("subject"),
                    context_type=INBOX_CONTEXT[service],
                    context_id=None,
                )
        except IntegrityError:
            thread = await self._threads.get_by_gmail_thread_id(
                session, gmail_thread_id
            )
            if thread is None:
                raise
        return RouteResult(thread=thread, unrouted=False)
