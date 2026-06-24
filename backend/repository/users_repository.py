from backend.entity.users_entity import UsersEntity
from backend.entity.user_emails_entity import UserEmailsEntity
from backend.entity.user_identities_entity import UserIdentitiesEntity
from backend.common.identity_type import IdentityType
from sqlalchemy import exists, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession


class UsersRepository:
    """
    Repository for handling database operations related to UsersEntity.
    """

    async def get_user_by_user_id(
        self, session: AsyncSession, user_id: int
    ) -> UsersEntity | None:
        """
        Retrieve a users entity by its user ID.

        This method expects an externally managed AsyncSession, typically provided
        by the service layer within a transactional context.

        Args:
            session (AsyncSession): The active async database session.
            user_id (int): The ID of the user to retrieve.

        Returns:
            UsersEntity | None: The matching user entity if found; otherwise None.
        """
        result = await session.execute(
            select(UsersEntity).where(UsersEntity.user_id == user_id)
        )

        return result.scalars().one_or_none()

    async def get_all_by_ids(self, session: AsyncSession, user_ids: list[int]):
        """
        Retrieve multiple users entities by a list of user IDs.

        Args:
            session (AsyncSession): The active async database session.
            user_ids (list[int]): A list of user IDs to retrieve.

        Returns:
            list[UsersEntity]: A list of matching user entities.
                               Returns an empty list if no matches are found.
        """
        if not user_ids:
            return []

        result = await session.execute(
            select(UsersEntity).where(UsersEntity.user_id.in_(user_ids))
        )
        return list(result.scalars().all())

    async def get_users_and_emails_by_ids(
        self, session: AsyncSession, user_ids: list[int]
    ) -> tuple[dict[int, UsersEntity], dict[int, list[UserEmailsEntity]]]:
        """
        Retrieve users and their confirmed email addresses by a list of user IDs.

        Args:
            session (AsyncSession): The active async database session.
            user_ids (list[int]): A list of user IDs to retrieve.

        Returns:
            tuple[dict[int, UsersEntity], dict[int, list[UserEmailsEntity]]]:
                A users map and an emails map both keyed by user_id.
                Returns empty dicts if user_ids is empty.
        """
        if not user_ids:
            return {}, {}

        result = await session.execute(
            select(UsersEntity, UserEmailsEntity)
            .outerjoin(
                UserEmailsEntity,
                UserEmailsEntity.user_id == UsersEntity.user_id,
            )
            .where(UsersEntity.user_id.in_(user_ids))
        )
        users_map: dict[int, UsersEntity] = {}
        emails_map: dict[int, list[UserEmailsEntity]] = {}
        for user, email in result.all():
            if user.user_id not in users_map:
                users_map[user.user_id] = user
                emails_map[user.user_id] = []
            if email is not None:
                emails_map[user.user_id].append(email)
        return users_map, emails_map

    async def get_user_by_subject_identifier(
        self, session: AsyncSession, sub: str
    ) -> UsersEntity | None:
        """
        Retrieve a users entity by its subject identifier.

        This method expects an externally managed AsyncSession, typically provided
        by the service layer within a transactional context.

        Args:
            session (AsyncSession): The active async database session.
            sub (string): The subject identifier of the user to retrieve.

        Returns:
            UsersEntity | None: The matching user entity if found; otherwise None.
        """
        result = await session.execute(
            select(UsersEntity).where(UsersEntity.subject_identifier == sub)
        )

        return result.scalars().one_or_none()

    async def get_user_by_primary_email(
        self, session: AsyncSession, primary_email: str
    ) -> UsersEntity | None:
        """
        Retrieve a users entity by its primary email.

        This method expects an externally managed AsyncSession, typically provided
        by the service layer within a transactional context.

        Args:
            session (AsyncSession): The active async database session.
            primary_email (string): The primary email of the user to retrieve.

        Returns:
            UsersEntity | None: The matching user entity if found; otherwise None.
        """
        result = await session.execute(
            select(UsersEntity).where(UsersEntity.primary_email == primary_email)
        )

        return result.scalars().one_or_none()

    async def upsert_users(
        self, session: AsyncSession, entity: UsersEntity
    ) -> UsersEntity:
        """
        Inserts or updates a UsersEntity object in the database.

        This method using session.merge() handles data persistence, it will
        updates the entity if the primary key exists, or inserts it otherwise

        Args:
            session (AsyncSession): The active async database session.
            entity: The UsersEntity object containing the user data.

        Returns:
            UsersEntity: The entity object synchronized with the database, reflecting
            the latest state, generated keys, and default values.
        """
        merged_entity = await session.merge(entity)
        await session.flush()

        return merged_entity

    async def list_users(
        self,
        session: AsyncSession,
        *,
        search: str | None = None,
        user_id: int | None = None,
        limit: int = 20,
        offset: int = 0,
        sort_by: str | None = None,
        order: str = "asc",
        is_super_admin: bool | None = None,
        user_type: str | None = None,
    ) -> tuple[list[tuple[UsersEntity, bool]], int]:
        """
        Paginated user list with optional case-insensitive substring search,
        sorting, and filtering.

        Args:
            session (AsyncSession): The active async database session.
            search (str | None): Case-insensitive substring over first_name /
                last_name / primary_email; None lists everyone.
            user_id (int | None): When not None, restricts results to the user
                with this exact ``user_id``. Applied in addition to ``search``.
            limit (int): Max rows to return.
            offset (int): Rows to skip (for pagination).
            sort_by (str | None): Column to sort by. Allowed values:
                ``"user_id"``, ``"first_name"``, ``"last_name"``,
                ``"preferred_name"``, ``"is_active"``, ``"is_super_admin"``,
                ``"user_type"`` (by the derived internal/external flag).
                Unknown or None values fall back to deterministic ``user_id``
                order.
            order (str): ``"asc"`` (default) or ``"desc"``. Only applied when
                ``sort_by`` resolves to a whitelisted column.
            is_super_admin (bool | None): When not None, restricts results to
                users whose ``is_super_admin`` flag matches this value.
            user_type (str | None): When ``"internal"`` keeps only users that
                have an INTERNAL identity row; when ``"external"`` keeps only
                users without one; otherwise no filter.

        Returns:
            tuple[list[tuple[UsersEntity, bool]], int]: (page rows where each
            element is (entity, is_internal), total number of rows matching all
            active filters across all pages).
        """
        internal_identity_exists = exists(
            select(UserIdentitiesEntity.identity_id).where(
                UserIdentitiesEntity.user_id == UsersEntity.user_id,
                UserIdentitiesEntity.identity_type == IdentityType.INTERNAL,
            )
        )

        # "user_type" sorts by the derived internal/external flag; ascending
        # puts external (no internal identity) before internal.
        _SORT_WHITELIST: dict[str, object] = {
            "user_id": UsersEntity.user_id,
            "first_name": UsersEntity.first_name,
            "last_name": UsersEntity.last_name,
            "preferred_name": UsersEntity.preferred_name,
            "is_active": UsersEntity.is_active,
            "is_super_admin": UsersEntity.is_super_admin,
            "user_type": internal_identity_exists,
        }

        filters = []
        if search:
            pattern = f"%{search.lower()}%"
            filters.append(
                or_(
                    func.lower(UsersEntity.first_name).like(pattern),
                    func.lower(UsersEntity.last_name).like(pattern),
                    func.lower(UsersEntity.primary_email).like(pattern),
                )
            )
        if user_id is not None:
            filters.append(UsersEntity.user_id == user_id)
        if is_super_admin is not None:
            filters.append(UsersEntity.is_super_admin == is_super_admin)
        if user_type == IdentityType.INTERNAL:
            filters.append(internal_identity_exists)
        elif user_type == IdentityType.EXTERNAL:
            filters.append(~internal_identity_exists)

        is_internal_col = internal_identity_exists.label("is_internal")

        # Build ORDER BY: whitelisted column (asc/desc) + user_id tiebreaker.
        sort_col = _SORT_WHITELIST.get(sort_by) if sort_by else None
        if sort_col is not None:
            primary_order = sort_col.desc() if order == "desc" else sort_col.asc()
            order_clauses = [primary_order, UsersEntity.user_id]
        else:
            order_clauses = [UsersEntity.user_id]

        total = await session.scalar(
            select(func.count()).select_from(UsersEntity).where(*filters)
        )
        result = await session.execute(
            select(UsersEntity, is_internal_col)
            .where(*filters)
            .order_by(*order_clauses)
            .limit(limit)
            .offset(offset)
        )
        return list(result.tuples().all()), int(total or 0)

    async def is_internal(self, session: AsyncSession, user_id: int) -> bool:
        """
        Returns True if the user has at least one identity_type='internal' row
        in user_identities.

        Args:
            session (AsyncSession): The active async database session.
            user_id (int): The user to check.

        Returns:
            bool: True if an INTERNAL identity row exists for this user.
        """
        result = await session.scalar(
            select(
                exists(
                    select(UserIdentitiesEntity.identity_id).where(
                        UserIdentitiesEntity.user_id == user_id,
                        UserIdentitiesEntity.identity_type == IdentityType.INTERNAL,
                    )
                )
            )
        )
        return bool(result)

    async def set_super_admin(
        self, session: AsyncSession, user_id: int, is_super_admin: bool
    ) -> int:
        """
        Set a user's super-admin flag.

        Args:
            session (AsyncSession): The active async database session.
            user_id (int): The user to update.
            is_super_admin (bool): The new flag value.

        Returns:
            int: The number of rows updated (0 if no user has ``user_id``).
        """
        result = await session.execute(
            update(UsersEntity)
            .where(UsersEntity.user_id == user_id)
            .values(is_super_admin=is_super_admin)
        )
        await session.flush()
        return result.rowcount
