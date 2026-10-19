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
from backend.common.name_utils import user_display_name


def ldap_from_addresses(addresses) -> str | None:
    """The Azure ldap an account carries, or None if it carries none.

    Azure knows people by ldap and purrf knows them by account; the corporate
    address is the whole of the join, so the ldap is read off it rather than
    stored a second time. Sorted, so that an account somehow holding two
    corporate addresses still reads the same way every time -- the directory
    join says that cannot happen, and if it does the answer must at least not
    move around between requests.

    Args:
        addresses: The account's email addresses, in any order.

    Returns:
        The local part of its corporate address, or None.
    """
    for address in sorted(addresses):
        if address.endswith(INTERNAL_GOOGLE_ACCOUNT_DOMAIN):
            return address.split("@")[0]
    return None


async def resolve_names_and_ldaps(
    session: AsyncSession,
    user_ids: list[int] | set[int],
    users_repository,
    user_emails_repository,
) -> tuple[dict[int, str], dict[int, str | None]]:
    """Resolves display names and LDAP identifiers for a collection of user IDs.

    Args:
        session: Active async session.
        user_ids: List or set of user IDs to resolve.
        users_repository: Repository providing get_all_by_ids.
        user_emails_repository: Repository providing get_emails_by_user_ids.

    Returns:
        A tuple of (name_by_id, ldap_by_id) mapping user IDs to their resolved values.
    """
    if not user_ids:
        return {}, {}

    users = await users_repository.get_all_by_ids(session, user_ids)
    name_by_id = {
        user.user_id: user_display_name(
            first_name=user.first_name,
            last_name=user.last_name,
            preferred_name=user.preferred_name,
        )
        for user in users
    }

    addresses_by_id = await user_emails_repository.get_emails_by_user_ids(
        session, user_ids
    )
    ldap_by_id = {
        uid: ldap_from_addresses(addresses)
        for uid, addresses in addresses_by_id.items()
    }

    return name_by_id, ldap_by_id


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

            * ``unresolved`` -- no account holds their corporate address
              confirmed, or the address points at a user row that is no
              longer there.
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
        # Unconfirmed addresses do not count: anyone can add one they do not
        # own. Someone whose address is unconfirmed lands in ``unresolved``.
        account_by_ldap = {
            owner_by_ldap[row.email]: row.user_id
            for row in rows
            if row.email in owner_by_ldap and row.otp_confirmed
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
