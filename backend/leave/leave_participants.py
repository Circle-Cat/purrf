"""Mapping Azure ldaps onto the purrf accounts a ledger row can point at.

A ledger row carries a ``user_id``, so everyone the engine pays has to be found
in the users table first. Azure knows people by ldap; purrf knows them by
account. The join is the corporate address, and only ``@circlecat.org`` can be
signed in with -- the ``u.`` domain is refused at the identity provider by
design -- so one address per person is the whole of it.

Nothing here is allowed to fail quietly. Somebody who cannot be matched gets no
accrual at all, and that is invisible in a balance -- so every reason for
leaving somebody out comes back named, for the job to report.
"""

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.constants import INTERNAL_GOOGLE_ACCOUNT_DOMAIN


@dataclass(frozen=True)
class ResolvedParticipants:
    """Who the engine can pay, and who it cannot, with the reason.

    Both exclusion lists are sorted so that two runs over the same directory
    produce the same report.
    """

    by_ldap: dict[str, int]
    unresolved: tuple[str, ...]
    not_internal: tuple[str, ...]


class LeaveParticipantResolver:
    """Resolves ldaps to purrf user ids for the leave jobs."""

    def __init__(self, logger, user_emails_repository, users_repository):
        """
        Args:
            logger: Structured logger.
            user_emails_repository (UserEmailsRepository): Address lookup.
            users_repository (UsersRepository): The internal-employee flag.
        """
        self.logger = logger
        self.user_emails_repository = user_emails_repository
        self.users_repository = users_repository

    async def resolve(
        self, session: AsyncSession, ldaps: list[str]
    ) -> ResolvedParticipants:
        """Matches each ldap to one purrf account.

        Args:
            session: Active async session.
            ldaps: Azure ldaps, from the employment profiles.

        Returns:
            The matches, plus a named list for each way of missing:

            * ``unresolved`` -- no account holds their corporate address, or
              the address points at a user row that is no longer there.
            * ``not_internal`` -- the account exists but ``users.is_internal``
              is false. That is the third admission condition, and it lives on
              the purrf row rather than in Azure, so it is checked here.
        """
        if not ldaps:
            return ResolvedParticipants({}, (), ())

        owner_by_ldap = {
            f"{ldap}{INTERNAL_GOOGLE_ACCOUNT_DOMAIN}": ldap for ldap in ldaps
        }
        rows = await self.user_emails_repository.list_by_emails(
            session, sorted(owner_by_ldap)
        )
        account_by_ldap = {
            owner_by_ldap[row.email]: row.user_id
            for row in rows
            if row.email in owner_by_ldap
        }

        users = await self.users_repository.get_all_by_ids(
            session, sorted(set(account_by_ldap.values()))
        )
        internal_by_id = {user.user_id: user.is_internal for user in users}

        by_ldap: dict[str, int] = {}
        unresolved: list[str] = []
        not_internal: list[str] = []

        for ldap in sorted(ldaps):
            user_id = account_by_ldap.get(ldap)
            if user_id is None or user_id not in internal_by_id:
                unresolved.append(ldap)
            elif not internal_by_id[user_id]:
                not_internal.append(ldap)
            else:
                by_ldap[ldap] = user_id

        return ResolvedParticipants(
            by_ldap=by_ldap,
            unresolved=tuple(unresolved),
            not_internal=tuple(not_internal),
        )
