"""Service behind the account console (/admin/accounts).

Answers the account-state questions the permission page never did: who is
deactivated, who is blocked, who did it and why, and how each account can sign
in. Deliberately separate from PermissionAdminService rather than an extension
of it -- the permission page stays untouched, and the two services coexisting
is the price of the two pages coexisting.

Entry-point service: every write method commits its own transaction.
"""

from backend.common.identity_type import IdentityType
from backend.common.name_utils import display_name_of
from backend.dto.user_account_dto import (
    SignInEmailDto,
    SignInIdentityDto,
    UserAccountRowDto,
    UserSignInMethodsDto,
)

_STATUS_ACTIVE = "active"
_STATUS_DEACTIVATED = "deactivated"
_STATUS_BLOCKED = "blocked"
# One filter, not two checkboxes: "active" is the absence of both states, and
# the other two read one flag each. Deactivation and blocking are independent,
# so "deactivated" deliberately says nothing about the block flag -- a user who
# is both still belongs in the deactivated view.
_STATUS_FILTERS: dict[str, tuple[bool | None, bool | None]] = {
    _STATUS_ACTIVE: (True, False),
    _STATUS_DEACTIVATED: (False, None),
    _STATUS_BLOCKED: (None, True),
}


class UserAccountService:
    def __init__(
        self,
        users_repository,
        user_emails_repository,
        user_identities_repository,
        block_request_repository,
        logger,
    ):
        """
        Args:
            users_repository (UsersRepository): Account rows -- the list, single
                lookups, and the deactivation/block state writes.
            user_emails_repository (UserEmailsRepository): Contact-email
                resolution for the list, and the sign-in email rows.
            user_identities_repository (UserIdentitiesRepository): The federated
                identities on the sign-in methods view.
            block_request_repository (BlockRequestRepository): Reads the
                caller's pending requests to flag rows in the list.
            logger (Logger): Injected logger.
        """
        self._users = users_repository
        self._user_emails = user_emails_repository
        self._user_identities = user_identities_repository
        self._block_requests = block_request_repository
        self._logger = logger

    async def list_accounts(
        self,
        session,
        *,
        caller_id: int,
        search: str | None = None,
        user_id: int | None = None,
        is_blocked: bool | None = None,
        status: str | None = None,
        user_type: str | None = None,
        search_blocked_reason: bool = False,
        limit: int,
        offset: int,
    ) -> tuple[list[UserAccountRowDto], int]:
        """
        A page of accounts with their state, the people behind that state, and
        whether the caller has a block request waiting on each one.

        Args:
            session (AsyncSession): The active async database session.
            caller_id (int): The operator viewing the page. Scopes
                ``has_pending_block_request``: a request is visible only to the
                reviewer it names.
            search (str | None): Case-insensitive substring over name/email.
            user_id (int | None): Restrict to one exact user.
            is_blocked (bool | None): Raw block-flag filter. Ignored when
                ``status`` is given, which is what the page actually sends.
            status (str | None): ``"active"`` / ``"deactivated"`` /
                ``"blocked"``, or None for no filter.
            user_type (str | None): ``"internal"`` / ``"external"`` / None.
            search_blocked_reason (bool): Also match ``search`` against the
                block reason. Off by default.
            limit (int): Max rows per page.
            offset (int): Rows to skip.

        Returns:
            tuple[list[UserAccountRowDto], int]: The page and the total match
            count across all pages.

        Raises:
            ValueError: If ``status`` is not a known value (surfaces as 400).
        """
        is_active = None
        if status is not None:
            if status not in _STATUS_FILTERS:
                raise ValueError("Unknown status")
            is_active, is_blocked = _STATUS_FILTERS[status]

        rows, total = await self._users.list_users(
            session,
            search=search,
            user_id=user_id,
            limit=limit,
            offset=offset,
            user_type=user_type,
            is_active=is_active,
            is_blocked=is_blocked,
            search_blocked_reason=search_blocked_reason,
        )

        contact_by_user_id = await self._user_emails.get_contact_emails_by_user_ids(
            session, [u.user_id for u, _ in rows]
        )
        name_by_id = await self._resolve_actor_names(session, rows)
        pending_targets = await self._pending_targets_for(session, caller_id)

        return [
            UserAccountRowDto(
                user_id=user.user_id,
                primary_email=contact_by_user_id.get(user.user_id, ""),
                first_name=user.first_name,
                last_name=user.last_name,
                preferred_name=user.preferred_name,
                user_type=(
                    IdentityType.INTERNAL if is_internal else IdentityType.EXTERNAL
                ),
                is_super_admin=user.is_super_admin,
                is_active=user.is_active,
                deactivated_at=user.deactivated_at,
                deactivated_by=user.deactivated_by,
                deactivated_by_name=name_by_id.get(user.deactivated_by),
                deactivated_reason=user.deactivated_reason,
                is_blocked=user.is_blocked,
                blocked_at=user.blocked_at,
                blocked_by=user.blocked_by,
                blocked_by_name=name_by_id.get(user.blocked_by),
                blocked_reason=user.blocked_reason,
                has_pending_block_request=user.user_id in pending_targets,
            )
            for user, is_internal in rows
        ], total

    async def get_sign_in_methods(
        self, session, user_id: int
    ) -> UserSignInMethodsDto:
        """
        Every way into one account: the addresses that can receive a sign-in
        code, and the federated identities linked to it.

        Both lists can legitimately be empty, and the page says so rather than
        rendering a blank block -- a user who has only ever used email codes has
        no identity row at all.

        Args:
            session (AsyncSession): The active async database session.
            user_id (int): The account to inspect.

        Returns:
            UserSignInMethodsDto: The account's emails and identities.

        Raises:
            ValueError: If no user exists with ``user_id`` (surfaces as 400).
        """
        await self._require_user(session, user_id)
        emails = await self._user_emails.list_by_user_id(session, user_id)
        identities = await self._user_identities.list_by_user_id(session, user_id)
        return UserSignInMethodsDto(
            emails=[
                SignInEmailDto(
                    email=e.email,
                    otp_confirmed=e.otp_confirmed,
                    is_primary=e.is_primary,
                    last_login_at=e.last_login_at,
                )
                for e in emails
            ],
            identities=[
                SignInIdentityDto(
                    subject_identifier=i.subject_identifier,
                    email_claim=i.email_claim,
                    linked_at=i.linked_at,
                    last_login_at=i.last_login_at,
                )
                for i in identities
            ],
        )

    async def deactivate(
        self, session, *, actor_id: int, user_id: int, note: str | None
    ) -> None:
        """
        Turn an account off at the user's own request. Commits.

        Args:
            session (AsyncSession): The active async database session.
            actor_id (int): The operator performing it.
            user_id (int): The account to deactivate.
            note (str | None): Optional free-text note. Deactivation is not a
                finding of fault, so no reason is demanded.

        Raises:
            ValueError: If no user exists with ``user_id`` (surfaces as 400).
            PermissionError: If the operator is deactivating themselves
                (surfaces as 403).
        """
        await self._require_user(session, user_id)
        if user_id == actor_id:
            # The only guard on this page. Deactivating yourself takes away the
            # door you would need to undo it.
            self._logger.warning(
                "Refused self-deactivation for user_id=%s", actor_id
            )
            raise PermissionError("You cannot deactivate your own account")
        await self._users.deactivate(session, user_id, actor_id, note)
        await session.commit()

    async def reactivate(self, session, *, actor_id: int, user_id: int) -> None:
        """
        Turn an account back on and clear the deactivation trio. Commits.
        Not guarded against acting on yourself: reactivation cannot lock anyone
        out.

        Args:
            session (AsyncSession): The active async database session.
            actor_id (int): The operator performing it, for the log.
            user_id (int): The account to reactivate.

        Raises:
            ValueError: If no user exists with ``user_id`` (surfaces as 400).
        """
        await self._require_user(session, user_id)
        await self._users.reactivate(session, user_id)
        await session.commit()

    async def unblock(self, session, user_id: int) -> None:
        """
        Lift a block. Idempotent: unblocking someone who is not blocked
        succeeds and changes nothing. Commits.

        Args:
            session (AsyncSession): The active async database session.
            user_id (int): The account to unblock.

        Raises:
            ValueError: If no user exists with ``user_id`` (surfaces as 400).
        """
        await self._require_user(session, user_id)
        await self._users.clear_block(session, user_id)
        await session.commit()

    async def _require_user(self, session, user_id: int):
        """
        Load a user or reject the request.

        Args:
            session (AsyncSession): The active async database session.
            user_id (int): The account to load.

        Returns:
            UsersEntity: The user row.

        Raises:
            ValueError: If no user exists with ``user_id``.
        """
        user = await self._users.get_user_by_user_id(session, user_id)
        if user is None:
            raise ValueError("User not found")
        return user

    async def _resolve_actor_names(self, session, rows) -> dict[int, str]:
        """
        Name every operator behind the state on this page, in one lookup.

        Rendering these as bare integers is the defect the account console
        exists to stop repeating, so the ids are collected across the whole page
        and resolved together; per row would be a query per id. An id with no
        users row is simply absent from the result, leaving its name None -- an
        audit trail can outlive the account it names.

        Args:
            session (AsyncSession): The active async database session.
            rows (list[tuple[UsersEntity, bool]]): The page from the repository.

        Returns:
            dict[int, str]: Display name by user id, for the ids that resolved.
        """
        ids = {
            actor_id
            for user, _ in rows
            for actor_id in (user.blocked_by, user.deactivated_by)
            if actor_id is not None
        }
        if not ids:
            return {}
        actors = await self._users.get_all_by_ids(session, sorted(ids))
        # Colleagues acting, not candidates: PUR-609 puts them on preferred_name.
        return {actor.user_id: display_name_of(actor) for actor in actors}

    async def _pending_targets_for(self, session, caller_id: int) -> set[int]:
        """
        The users this caller has a block request waiting on.

        Scoped to the caller on purpose: a request is addressed to the one
        reviewer it names, and nobody else may learn it exists. One query for
        the page, not one per row.

        Args:
            session (AsyncSession): The active async database session.
            caller_id (int): The operator viewing the page.

        Returns:
            set[int]: target_user_id of the caller's pending requests.
        """
        pending = await self._block_requests.list_pending_for_reviewer(
            session, caller_id
        )
        return {row.target_user_id for row in pending}
