from datetime import datetime

from backend.entity.user_identities_entity import UserIdentitiesEntity
from backend.entity.users_entity import UsersEntity
from sqlalchemy import delete, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession


class UserIdentitiesRepository:
    """
    Repository for handling database operations related to UserIdentitiesEntity.
    """

    async def get_user_and_login_state_by_sub(
        self, session: AsyncSession, sub: str
    ) -> tuple[UsersEntity, int, datetime | None] | None:
        """
        Resolve the owning user plus the identity's id and current
        last_login_at from an Auth0 sub in a single JOIN.

        Backs the hot authentication path: returns everything bootstrap needs
        — the UsersEntity (for user_id / is_active), the identity_id, and the
        stored last_login_at — in one round-trip, instead of a sub lookup
        followed by a separate users fetch. Returning last_login_at lets the
        caller skip the follow-up UPDATE entirely when the token's iat has not
        advanced (the common case within a session), so a steady-state request
        costs a single read. The INNER JOIN means an identity with no surviving
        user yields None, the same "not found" outcome as a missing sub; an FK
        on user_identities.user_id guarantees that orphan case cannot actually
        arise.

        Args:
            session (AsyncSession): The active async database session.
            sub (str): Auth0 sub claim (e.g., 'google-oauth2|123' or 'email|abc').

        Returns:
            tuple[UsersEntity, int, datetime | None] | None: (owning user,
            identity_id, stored last_login_at) on hit; None on miss.
        """
        result = await session.execute(
            select(
                UsersEntity,
                UserIdentitiesEntity.identity_id,
                UserIdentitiesEntity.last_login_at,
            )
            .join(
                UserIdentitiesEntity,
                UserIdentitiesEntity.user_id == UsersEntity.user_id,
            )
            .where(UserIdentitiesEntity.subject_identifier == sub)
        )
        row = result.one_or_none()
        if row is None:
            return None
        return row[0], row[1], row[2]

    async def list_by_user_id(
        self, session: AsyncSession, user_id: int
    ) -> list[UserIdentitiesEntity]:
        """
        Return all of this user's identity rows, ordered by identity_id, to back
        the Settings comprehensive view (internal + external identities).

        Args:
            session (AsyncSession): The active async database session.
            user_id (int): user_id whose identity rows to list.

        Returns:
            list[UserIdentitiesEntity]: The user's identity rows ordered by
            identity_id; empty when the user has none.
        """
        result = await session.execute(
            select(UserIdentitiesEntity)
            .where(UserIdentitiesEntity.user_id == user_id)
            .order_by(UserIdentitiesEntity.identity_id)
        )
        return list(result.scalars().all())

    async def get_by_id(
        self, session: AsyncSession, identity_id: int
    ) -> UserIdentitiesEntity | None:
        """
        Fetch a single identity row by its primary key.

        Args:
            session (AsyncSession): The active async database session.
            identity_id (int): identity_id to look up.

        Returns:
            UserIdentitiesEntity | None: The row if found; otherwise None.
        """
        result = await session.execute(
            select(UserIdentitiesEntity).where(
                UserIdentitiesEntity.identity_id == identity_id
            )
        )
        return result.scalars().one_or_none()

    async def delete(self, session: AsyncSession, identity_id: int) -> None:
        """
        Remove one identity row by primary key, backing the unlink flow.

        Args:
            session (AsyncSession): The active async database session.
            identity_id (int): identity_id of the row to delete.
        """
        await session.execute(
            delete(UserIdentitiesEntity).where(
                UserIdentitiesEntity.identity_id == identity_id
            )
        )
        await session.flush()

    async def find_swappable_by_email(
        self, session: AsyncSession, email_claim: str
    ) -> UserIdentitiesEntity | None:
        """
        Look up a migration-backfilled identity by email_claim.

        Restricted to mock rows (subject_identifier 'manual|%', the backfill
        convention) so already-linked real subs are never matched — this both
        prevents a spurious MultipleResultsFound and avoids re-linking a live
        identity.

        Args:
            session (AsyncSession): The active async database session.
            email_claim (str): Lowercased email to match.

        Returns:
            UserIdentitiesEntity | None: Matching mock row, or None.
        """
        result = await session.execute(
            select(UserIdentitiesEntity).where(
                UserIdentitiesEntity.email_claim == email_claim,
                UserIdentitiesEntity.subject_identifier.like("manual|%"),
            )
        )
        return result.scalars().one_or_none()

    async def upsert_identity(
        self, session: AsyncSession, entity: UserIdentitiesEntity
    ) -> UserIdentitiesEntity:
        """
        Inserts or updates a UserIdentitiesEntity in the database.

        Uses session.merge() — inserts if no PK is set, otherwise updates the
        matching row.

        Args:
            session (AsyncSession): The active async database session.
            entity (UserIdentitiesEntity): The identity row to persist.

        Returns:
            UserIdentitiesEntity: The entity synchronized with the database.
        """
        merged_entity = await session.merge(entity)
        await session.flush()

        return merged_entity

    async def update_last_login(
        self, session: AsyncSession, identity_id: int, login_at: datetime
    ) -> None:
        """
        Update last_login_at to `login_at` only if it is newer than the
        stored value (or stored is NULL).

        Called after a successful step-1 sub lookup so that future audits /
        cleanup jobs can see when this identity last logged in. The
        only-if-newer guard avoids redundant writes; the caller passes the
        Auth0 token iat (CF JWT `custom.iat`), which only advances on a real
        re-authentication, not on CF Access silent refresh.

        Args:
            session (AsyncSession): The active async database session.
            identity_id (int): identity_id of the row to touch.
            login_at (datetime): Candidate value, the Auth0 iat as a
                timezone-aware datetime.
        """
        await session.execute(
            update(UserIdentitiesEntity)
            .where(
                UserIdentitiesEntity.identity_id == identity_id,
                or_(
                    UserIdentitiesEntity.last_login_at.is_(None),
                    UserIdentitiesEntity.last_login_at < login_at,
                ),
            )
            .values(last_login_at=login_at)
        )
        await session.flush()

    async def get_google_subs_by_user_ids(
        self, session: AsyncSession, user_ids: list[int]
    ) -> dict[int, list[str]]:
        """
        Map each user_id to all of its google-oauth2 subject_identifiers.

        Backs Meet attendance's local UID->email cache: the Google participant
        log keys on the numeric Google user id, which is the suffix of a
        ``google-oauth2|<id>`` sub. A user who has linked more than one Google
        account has several such subs, and every one must resolve from the cache,
        so the value is a list. Only google-oauth2 identities are returned; a
        user without one is omitted. An empty input short-circuits without a
        query.

        Args:
            session (AsyncSession): The active async database session.
            user_ids (list[int]): user_ids whose Google subs to fetch.

        Returns:
            dict[int, list[str]]: {user_id: [google-oauth2 subject_identifier, ...]}
            for users that have at least one Google identity; users without one
            are omitted.
        """
        if not user_ids:
            return {}
        result = await session.execute(
            select(
                UserIdentitiesEntity.user_id,
                UserIdentitiesEntity.subject_identifier,
            ).where(
                UserIdentitiesEntity.user_id.in_(user_ids),
                UserIdentitiesEntity.subject_identifier.like("google-oauth2|%"),
            )
        )
        subs_by_user_id: dict[int, list[str]] = {}
        for user_id, sub in result.all():
            subs_by_user_id.setdefault(user_id, []).append(sub)
        return subs_by_user_id

    async def get_by_subject_identifier(
        self, session: AsyncSession, subject_identifier: str
    ) -> UserIdentitiesEntity | None:
        """
        Fetch a single identity row by its Auth0 subject identifier.

        Args:
            session (AsyncSession): The active async database session.
            subject_identifier (str): Auth0 sub (e.g. 'google-oauth2|123').

        Returns:
            UserIdentitiesEntity | None: The row if found; otherwise None.
        """
        result = await session.execute(
            select(UserIdentitiesEntity).where(
                UserIdentitiesEntity.subject_identifier == subject_identifier
            )
        )
        return result.scalars().one_or_none()
