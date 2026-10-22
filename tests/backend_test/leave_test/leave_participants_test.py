"""Mapping Azure ldaps onto purrf accounts before anything is accrued.

Everyone the leave engine pays has to be found in the purrf users table, since
a ledger row points at a user_id. Somebody who cannot be found gets no accrual,
so the one thing this must never do is fail quietly.
"""

from unittest import IsolatedAsyncioTestCase, main
from unittest.mock import AsyncMock, MagicMock

from backend.leave.leave_participants import (
    LeaveParticipantResolver,
    resolve_names_and_ldaps,
)


def _email_row(email, user_id, confirmed=True):
    row = MagicMock()
    row.email = email
    row.user_id = user_id
    row.otp_confirmed = confirmed
    return row


def _user(user_id, is_internal=True):
    row = MagicMock()
    row.user_id = user_id
    row.is_internal = is_internal
    return row


class LeaveParticipantResolverTest(IsolatedAsyncioTestCase):
    def setUp(self):
        self.logger = MagicMock()
        self.user_emails_repository = MagicMock()
        self.user_emails_repository.list_by_emails = AsyncMock(return_value=[])
        self.users_repository = MagicMock()
        self.users_repository.get_all_by_ids = AsyncMock(return_value=[])
        self.session = MagicMock()
        self.resolver = LeaveParticipantResolver(
            logger=self.logger,
            user_emails_repository=self.user_emails_repository,
            users_repository=self.users_repository,
        )

    async def test_a_google_workspace_address_resolves(self):
        self.user_emails_repository.list_by_emails.return_value = [
            _email_row("ann@circlecat.org", 11)
        ]
        self.users_repository.get_all_by_ids.return_value = [_user(11)]

        resolved = await self.resolver.resolve(self.session, ["ann"])

        self.assertEqual(resolved.by_ldap, {"ann": 11})

    async def test_only_the_signin_domain_is_asked_for(self):
        """The u. domain is refused at the identity provider by design, so an
        address there can never be the account a person signs in with."""
        await self.resolver.resolve(self.session, ["ann"])

        asked = self.user_emails_repository.list_by_emails.await_args.args[1]
        self.assertEqual(asked, ["ann@circlecat.org"])

    async def test_an_address_on_the_other_internal_domain_is_ignored(self):
        """Even if such a row exists, it is not asked for -- and a row the
        query did not ask for must not resolve anybody."""
        self.user_emails_repository.list_by_emails.return_value = [
            _email_row("ann@u.circlecat.org", 99)
        ]

        resolved = await self.resolver.resolve(self.session, ["ann"])

        self.assertEqual(resolved.by_ldap, {})
        self.assertEqual(resolved.unresolved, ("ann",))

    async def test_an_unconfirmed_address_is_reported_not_paid(self):
        """Anyone can add an address without owning it, so an unconfirmed one
        does not tie an ldap to an account. It is named in the report rather
        than dropped, so an employee who never confirmed is still seen."""
        self.user_emails_repository.list_by_emails.return_value = [
            _email_row("ann@circlecat.org", 11, confirmed=False)
        ]
        self.users_repository.get_all_by_ids.return_value = [_user(11)]

        resolved = await self.resolver.resolve(self.session, ["ann"])

        self.assertEqual(resolved.by_ldap, {})
        self.assertEqual(resolved.unresolved, ("ann",))

    async def test_someone_with_no_purrf_account_is_reported(self):
        resolved = await self.resolver.resolve(self.session, ["ghost"])

        self.assertEqual(resolved.unresolved, ("ghost",))
        self.assertEqual(resolved.by_ldap, {})

    async def test_an_account_that_is_not_internal_is_excluded_and_reported(self):
        """is_internal is the third admission condition, and it lives on the
        purrf row rather than in Azure, so this is where it is checked."""
        self.user_emails_repository.list_by_emails.return_value = [
            _email_row("ann@circlecat.org", 11)
        ]
        self.users_repository.get_all_by_ids.return_value = [
            _user(11, is_internal=False)
        ]

        resolved = await self.resolver.resolve(self.session, ["ann"])

        self.assertEqual(resolved.not_internal, ("ann",))
        self.assertEqual(resolved.by_ldap, {})

    async def test_an_account_row_that_has_vanished_counts_as_unresolved(self):
        """The address points at a user_id with no users row behind it. Left
        unhandled this would be a KeyError in the middle of a payroll job."""
        self.user_emails_repository.list_by_emails.return_value = [
            _email_row("ann@circlecat.org", 11)
        ]
        self.users_repository.get_all_by_ids.return_value = []

        resolved = await self.resolver.resolve(self.session, ["ann"])

        self.assertEqual(resolved.unresolved, ("ann",))

    async def test_resolving_nobody_queries_nothing(self):
        resolved = await self.resolver.resolve(self.session, [])

        self.assertEqual(resolved.by_ldap, {})
        self.user_emails_repository.list_by_emails.assert_not_awaited()

    async def test_the_reports_are_ordered_so_two_runs_read_the_same(self):
        resolved = await self.resolver.resolve(self.session, ["zoe", "ann", "mia"])

        self.assertEqual(resolved.unresolved, ("ann", "mia", "zoe"))

    async def test_resolve_names_and_ldaps_empty_user_ids(self):
        """Should return empty dictionaries immediately without querying repositories when user_ids is empty."""

        name_by_id, ldap_by_id = await resolve_names_and_ldaps(
            self.session,
            [],
            self.users_repository,
            self.user_emails_repository,
        )

        self.assertEqual(name_by_id, {})
        self.assertEqual(ldap_by_id, {})
        self.users_repository.get_all_by_ids.assert_not_called()
        self.user_emails_repository.get_emails_by_user_ids.assert_not_called()

    async def test_resolve_names_and_ldaps_resolves_correctly(self):
        """Verify user records and emails correctly resolve into name_by_id and ldap_by_id mappings."""

        user_mock = MagicMock()
        user_mock.user_id = 44
        user_mock.first_name = "Wen"
        user_mock.last_name = "Zhang"
        user_mock.preferred_name = None

        self.users_repository.get_all_by_ids = AsyncMock(return_value=[user_mock])
        self.user_emails_repository.get_emails_by_user_ids = AsyncMock(
            return_value={44: ["wen.zhang@circlecat.org"]}
        )

        name_by_id, ldap_by_id = await resolve_names_and_ldaps(
            self.session,
            [44],
            self.users_repository,
            self.user_emails_repository,
        )

        self.assertEqual(name_by_id, {44: "Wen Zhang"})
        self.assertEqual(ldap_by_id, {44: "wen.zhang"})


if __name__ == "__main__":
    main()
