"""Service for the recruiting blacklist admin page: list + unblock.

Kept separate from BoardService: board_service's writes (advance, reject,
blacklist) all act on a specific application. Listing and unblocking act on
the users table directly, unscoped to any application or posting.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from backend.dto.blacklist_dto import BlacklistEntryDto


class BlacklistService:
    """Reads and clears the org-wide user blacklist."""

    def __init__(self, users_repository):
        """
        Args:
            users_repository (UsersRepository): Blocked-user reads/writes.
        """
        self.users_repository = users_repository

    async def list_blacklist(
        self, session: AsyncSession, search: str | None = None
    ) -> list[BlacklistEntryDto]:
        """
        List every currently-blocked user, optionally filtered by search.

        Args:
            session (AsyncSession): Active database async session.
            search (str | None): Case-insensitive substring over
                name/email/reason; None returns everyone blocked.

        Returns:
            list[BlacklistEntryDto]: Blocked users, most recently blocked first.
        """
        users = await self.users_repository.list_blocked_users(
            session, search=search
        )
        return [
            BlacklistEntryDto(
                user_id=user.user_id,
                name=f"{user.first_name} {user.last_name}".strip(),
                email=user.primary_email,
                reason=user.blocked_reason or "",
                blocked_at=user.blocked_at,
            )
            for user in users
        ]

    async def unblock(self, session: AsyncSession, user_id: int) -> None:
        """
        Clear a user's block state. Idempotent (see
        UsersRepository.clear_block).

        Args:
            session (AsyncSession): Active database async session.
            user_id (int): The user to unblock.
        """
        await self.users_repository.clear_block(session, user_id)
        await session.commit()
