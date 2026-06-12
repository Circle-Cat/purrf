from backend.entity.user_emails_entity import UserEmailsEntity
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class UserEmailsRepository:
    """
    Repository for handling database operations related to UserEmailsEntity.

    Email values are stored already normalized (lowercased) by the application
    layer, so equality lookups here compare against the normalized address
    directly.
    """

    async def get_by_user_and_email(
        self, session: AsyncSession, user_id: int, email: str
    ) -> UserEmailsEntity | None:
        """
        Fetch this user's row for `email`, or None — lets a verify upsert decide
        between flipping an existing row to confirmed and inserting a new one.
        """
        result = await session.execute(
            select(UserEmailsEntity).where(
                UserEmailsEntity.user_id == user_id,
                UserEmailsEntity.email == email,
            )
        )
        return result.scalars().one_or_none()

    async def exists_confirmed_on_other_user(
        self, session: AsyncSession, email: str, user_id: int
    ) -> bool:
        """
        Whether `email` is already a confirmed contact on a *different* account —
        the guard that stops one user from claiming another's verified address.
        """
        result = await session.execute(
            select(UserEmailsEntity.email_id)
            .where(
                UserEmailsEntity.email == email,
                UserEmailsEntity.otp_confirmed.is_(True),
                UserEmailsEntity.user_id != user_id,
            )
            .limit(1)
        )
        return result.first() is not None

    async def has_confirmed(self, session: AsyncSession, user_id: int) -> bool:
        """
        Whether the user has any OTP-confirmed email — the hard-wall predicate:
        a user with none is dangling and must verify before acting.
        """
        result = await session.execute(
            select(UserEmailsEntity.email_id)
            .where(
                UserEmailsEntity.user_id == user_id,
                UserEmailsEntity.otp_confirmed.is_(True),
            )
            .limit(1)
        )
        return result.first() is not None

    async def has_primary(self, session: AsyncSession, user_id: int) -> bool:
        """Whether the user already has a primary email, used to auto-promote the first confirmed one."""
        result = await session.execute(
            select(UserEmailsEntity.email_id)
            .where(
                UserEmailsEntity.user_id == user_id,
                UserEmailsEntity.is_primary.is_(True),
            )
            .limit(1)
        )
        return result.first() is not None

    async def upsert_email(
        self, session: AsyncSession, entity: UserEmailsEntity
    ) -> UserEmailsEntity:
        """
        Inserts or updates a UserEmailsEntity in the database.

        Uses session.merge() — inserts if no PK is set, otherwise updates the
        matching row.

        Args:
            session (AsyncSession): The active async database session.
            entity (UserEmailsEntity): The email row to persist.

        Returns:
            UserEmailsEntity: The entity synchronized with the database.
        """
        merged_entity = await session.merge(entity)
        await session.flush()

        return merged_entity
