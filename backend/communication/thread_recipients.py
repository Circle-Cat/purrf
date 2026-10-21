"""Who hears about new mail on one thread: whoever wrote into it through Purrf.

Shared by every domain's email resolvers; each names its own fallback.
"""

from collections.abc import Awaitable, Callable, Iterable

from sqlalchemy.ext.asyncio import AsyncSession

from backend.repository.email_message_repository import EmailMessageRepository

# Stateless, so one module-level instance serves every resolver.
_messages = EmailMessageRepository()


async def thread_senders(session: AsyncSession, thread_id: int) -> set[int]:
    """The users who sent a message in the thread through Purrf.

    Args:
        session (AsyncSession): Session inside the caller's open transaction.
        thread_id (int): The thread.

    Returns:
        set[int]: Their user ids; empty when every message came from Gmail itself.
    """
    return await _messages.list_sender_ids_by_thread(session, thread_id)


async def thread_senders_else(
    session: AsyncSession,
    thread_id: int,
    fallback: Callable[[], Awaitable[Iterable[int]]],
) -> set[int]:
    """The thread's senders, or whoever ``fallback`` names when there are none.

    Args:
        session (AsyncSession): Session inside the caller's open transaction.
        thread_id (int): The thread.
        fallback: Called only when nobody sent through Purrf.

    Returns:
        set[int]: User ids.
    """
    senders = await thread_senders(session, thread_id)
    if senders:
        return senders
    return set(await fallback())
