from datetime import datetime

from backend.entity.user_emails_entity import UserEmailsEntity
from sqlalchemy import delete, or_, select, update
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

    async def list_by_user_id(
        self, session: AsyncSession, user_id: int
    ) -> list[UserEmailsEntity]:
        """
        Return all of this user's email rows (confirmed and pending), ordered by
        email_id, to back the Settings comprehensive view.

        Args:
            session (AsyncSession): The active async database session.
            user_id (int): user_id whose email rows to list.

        Returns:
            list[UserEmailsEntity]: The user's email rows ordered by email_id;
            empty when the user has none.
        """
        result = await session.execute(
            select(UserEmailsEntity)
            .where(UserEmailsEntity.user_id == user_id)
            .order_by(UserEmailsEntity.email_id)
        )
        return list(result.scalars().all())

    async def get_emails_by_user_ids(
        self, session: AsyncSession, user_ids: list[int]
    ) -> dict[int, list[str]]:
        """
        Map each user_id to all of its email addresses, primary or not,
        regardless of otp_confirmed.

        Backs Meet attendance matching, which matches a meeting participant
        against any of a mentor/mentee's known addresses. A user with no
        email rows is omitted from the map. An empty input short-circuits
        without a query.

        Args:
            session (AsyncSession): The active async database session.
            user_ids (list[int]): user_ids whose emails to fetch.

        Returns:
            dict[int, list[str]]: {user_id: [email, ...]} for users that have
            at least one row; users without any are omitted.
        """
        if not user_ids:
            return {}
        result = await session.execute(
            select(
                UserEmailsEntity.user_id,
                UserEmailsEntity.email,
            ).where(UserEmailsEntity.user_id.in_(user_ids))
        )
        emails_by_user_id: dict[int, list[str]] = {}
        for user_id, email in result.all():
            emails_by_user_id.setdefault(user_id, []).append(email)
        return emails_by_user_id

    async def get_contact_emails_by_user_ids(
        self, session: AsyncSession, user_ids: list[int]
    ) -> dict[int, str]:
        """
        Map each user_id to its best contact address: the primary row when one
        exists, otherwise the user's oldest claim (lowest email_id) — the
        address seeded from their login, i.e. what the legacy
        users.primary_email column held. This is the read that replaces that
        column.

        A user with no email rows is omitted from the map. An empty input
        short-circuits without a query.

        Args:
            session (AsyncSession): The active async database session.
            user_ids (list[int]): user_ids whose contact address to fetch.

        Returns:
            dict[int, str]: {user_id: email} for users that have at least one
            row; users without any are omitted.
        """
        if not user_ids:
            return {}
        result = await session.execute(
            select(UserEmailsEntity.user_id, UserEmailsEntity.email)
            .distinct(UserEmailsEntity.user_id)
            .where(UserEmailsEntity.user_id.in_(user_ids))
            .order_by(
                UserEmailsEntity.user_id,
                UserEmailsEntity.is_primary.desc(),
                UserEmailsEntity.email_id.asc(),
            )
        )
        return {user_id: email for user_id, email in result.all()}

    async def get_contact_email(
        self, session: AsyncSession, user_id: int
    ) -> str | None:
        """
        Single-user convenience over :meth:`get_contact_emails_by_user_ids`.

        Args:
            session (AsyncSession): The active async database session.
            user_id (int): The user whose contact address to fetch.

        Returns:
            str | None: The user's contact address, or None when they have no
            email rows.
        """
        contact_by_user_id = await self.get_contact_emails_by_user_ids(
            session, [user_id]
        )
        return contact_by_user_id.get(user_id)

    async def exists_on_other_user(
        self, session: AsyncSession, email: str, user_id: int
    ) -> bool:
        """
        Whether `email` is claimed by a *different* account, confirmed or not —
        the guard that stops one user from claiming an address another account
        already holds. Addresses are globally exclusive (unique index
        ``uq_user_emails_email``), so even an unverified claim makes the
        address unavailable to everyone else.

        Args:
            session (AsyncSession): Active database async session.
            email (str): Normalized (lowercased) address to check.
            user_id (int): The caller's user_id, excluded from the match.

        Returns:
            bool: True when another account has any row for the address.
        """
        result = await session.execute(
            select(UserEmailsEntity.email_id)
            .where(
                UserEmailsEntity.email == email,
                UserEmailsEntity.user_id != user_id,
            )
            .limit(1)
        )
        return result.first() is not None

    async def get_by_email(
        self, session: AsyncSession, email: str
    ) -> UserEmailsEntity | None:
        """
        Fetch the row claiming `email`, confirmed or not, regardless of which
        user owns it. Addresses are globally exclusive (unique index
        ``uq_user_emails_email``), so a plain scalar lookup suffices.

        Args:
            session (AsyncSession): Active database async session.
            email (str): Normalized (lowercased) address to look up.

        Returns:
            UserEmailsEntity | None: The claiming row, or None when no account
            has the address.
        """
        result = await session.execute(
            select(UserEmailsEntity).where(UserEmailsEntity.email == email).limit(1)
        )
        return result.scalar_one_or_none()

    async def get_confirmed_by_email(
        self, session: AsyncSession, email: str
    ) -> UserEmailsEntity | None:
        """
        Fetch the OTP-confirmed row owning `email`, regardless of which user
        owns it — trusted-assertion routing (step 2.5 in
        UserIdentityService.create_or_swap_user) uses it to resolve a login
        for an already-confirmed address straight into its owning account.
        At most one confirmed row can exist per address (cross-account
        claims are blocked at confirm time), so a plain scalar lookup
        suffices.

        Args:
            session (AsyncSession): Active database async session.
            email (str): Normalized (lowercased) address to look up.

        Returns:
            UserEmailsEntity | None: The confirmed row, or None when the
            address has never been OTP-confirmed by any account.
        """
        result = await session.execute(
            select(UserEmailsEntity)
            .where(
                UserEmailsEntity.email == email,
                UserEmailsEntity.otp_confirmed.is_(True),
            )
            .limit(1)
        )
        return result.scalar_one_or_none()

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

    async def get_primary(
        self, session: AsyncSession, user_id: int
    ) -> UserEmailsEntity | None:
        """
        Fetch the user's current primary email row, or None if they have none.

        Backs the set-primary step-up flow, which sends the OTP to the existing
        primary and snapshots it before swapping. The partial unique index
        ``user_emails_primary_idx`` guarantees at most one primary per user, so
        ``one_or_none`` is safe.

        Args:
            session (AsyncSession): The active async database session.
            user_id (int): user_id whose primary email to fetch.

        Returns:
            UserEmailsEntity | None: The primary row, or None when none is set.
        """
        result = await session.execute(
            select(UserEmailsEntity).where(
                UserEmailsEntity.user_id == user_id,
                UserEmailsEntity.is_primary.is_(True),
            )
        )
        return result.scalars().one_or_none()

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

    async def get_by_id(
        self, session: AsyncSession, email_id: int
    ) -> UserEmailsEntity | None:
        """
        Fetch a single email row by its primary key.

        Backs ownership checks where the caller supplies an email_id from a URL
        path and the service must verify the row exists and belongs to them.

        Args:
            session (AsyncSession): The active async database session.
            email_id (int): Primary key of the email row to fetch.

        Returns:
            UserEmailsEntity | None: The matching row, or None when no row has
            that email_id.
        """
        result = await session.execute(
            select(UserEmailsEntity).where(UserEmailsEntity.email_id == email_id)
        )
        return result.scalars().one_or_none()

    async def set_primary(
        self, session: AsyncSession, user_id: int, email_id: int
    ) -> None:
        """
        Move the user's primary flag onto ``email_id`` in a single transaction.

        Clears the user's current primary, then sets the target — the same two
        UPDATEs the spec prescribes. The partial unique index
        ``user_emails_primary_idx`` guarantees at most one primary per user even
        under concurrent calls. Flushes but does not commit; the caller owns the
        transaction boundary.

        Args:
            session (AsyncSession): The active async database session.
            user_id (int): user_id owning both the old and new primary rows.
            email_id (int): Primary key of the row to promote to primary.
        """
        await session.execute(
            update(UserEmailsEntity)
            .where(
                UserEmailsEntity.user_id == user_id,
                UserEmailsEntity.is_primary.is_(True),
            )
            .values(is_primary=False)
        )
        await session.execute(
            update(UserEmailsEntity)
            .where(UserEmailsEntity.email_id == email_id)
            .values(is_primary=True)
        )
        await session.flush()

    async def delete(self, session: AsyncSession, email_id: int) -> None:
        """
        Remove one email row by primary key, backing the unlink flow's drop of a
        sign-in identity's synced contact address.

        Flushes but does not commit; the caller owns the transaction boundary.

        Args:
            session (AsyncSession): The active async database session.
            email_id (int): Primary key of the email row to delete.
        """
        await session.execute(
            delete(UserEmailsEntity).where(UserEmailsEntity.email_id == email_id)
        )
        await session.flush()

    async def update_last_login(
        self, session: AsyncSession, email_id: int, login_dt: datetime
    ) -> None:
        """
        Stamp this email's last_login_at to ``login_dt`` only when it is newer
        than the stored value (or unset). Mirrors the identity repo's
        if-newer update so out-of-order/replayed tokens never regress the time.

        Args:
            session (AsyncSession): The active async database session.
            email_id (int): The user_emails row to stamp.
            login_dt (datetime): The login instant (JWT iat as tz-aware datetime).
        """
        await session.execute(
            update(UserEmailsEntity)
            .where(
                UserEmailsEntity.email_id == email_id,
                or_(
                    UserEmailsEntity.last_login_at.is_(None),
                    UserEmailsEntity.last_login_at < login_dt,
                ),
            )
            .values(last_login_at=login_dt)
        )
        await session.flush()
