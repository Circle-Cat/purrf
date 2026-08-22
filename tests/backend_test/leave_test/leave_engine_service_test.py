"""The two scheduled jobs: weekly accrual, and the annual close on 1 January.

Both are thin loops over arithmetic that is already pinned elsewhere. What is
tested here is the loop's judgement -- who is paid, who is skipped and why, and
what a second run does -- because every one of those mistakes produces a wrong
number rather than an error.
"""

import datetime
import json
from decimal import Decimal
from unittest import IsolatedAsyncioTestCase, main
from unittest.mock import AsyncMock, MagicMock, patch

from backend.common.leave_enums import LeaveEntryType
from backend.leave.leave_engine_service import LeaveEngineService
from backend.leave.leave_participants import ResolvedParticipants

MID_YEAR = datetime.date(2026, 7, 8)
NEW_YEAR = datetime.date(2027, 1, 1)


def _profile(
    level="L3",
    annual_hours=80,
    hire_date="2024-03-01",
    leave_date=None,
    account_enabled=True,
):
    return json.dumps({
        "level": level,
        "annual_hours": annual_hours,
        "hire_date": hire_date,
        "leave_date": leave_date,
        "manager_ldap": "bob",
        "account_enabled": account_enabled,
        "problems": [],
    })


class LeaveEngineServiceTest(IsolatedAsyncioTestCase):
    def setUp(self):
        self.logger = MagicMock()
        self.redis_client = MagicMock()
        self.retry_utils = MagicMock()
        self.retry_utils.get_retry_on_transient = lambda fn, *a, **kw: fn(*a, **kw)
        self.resolver = MagicMock()
        self.resolver.resolve = AsyncMock()
        self.repository = MagicMock()
        self.repository.add_entries = AsyncMock()
        self.repository.sum_weekly_accrual = AsyncMock(return_value=Decimal("0.00"))
        self.repository.latest_level_change_date = AsyncMock(return_value=None)
        self.repository.balance = AsyncMock(return_value=Decimal("0.00"))
        self.session = MagicMock()
        self.session.commit = AsyncMock()
        self.repository.balances_by_user_ids = AsyncMock(return_value={})
        self.users = MagicMock()
        self.users.get_all_by_ids = AsyncMock(return_value=[])
        self.service = LeaveEngineService(
            logger=self.logger,
            redis_client=self.redis_client,
            retry_utils=self.retry_utils,
            participant_resolver=self.resolver,
            leave_ledger_repository=self.repository,
            users_repository=self.users,
        )

    def _directory(self, profiles, resolved=None):
        self.redis_client.hgetall.return_value = profiles
        self.resolver.resolve.return_value = resolved or ResolvedParticipants(
            by_ldap={ldap: 10 + index for index, ldap in enumerate(sorted(profiles))},
            unresolved=(),
            not_internal=(),
        )

    def _written(self):
        if not self.repository.add_entries.await_args_list:
            return []
        return [
            entry
            for call in self.repository.add_entries.await_args_list
            for entry in call.args[1]
        ]


class TestWeeklyAccrual(LeaveEngineServiceTest):
    async def test_a_week_is_paid_as_a_weekly_accrual_dated_today(self):
        self._directory({"ann": _profile()})

        report = await self.service.run_weekly_accrual(self.session, today=MID_YEAR)

        entry = self._written()[0]
        self.assertEqual(entry.entry_type, LeaveEntryType.WEEKLY_ACCRUAL)
        self.assertEqual(entry.user_id, 10)
        self.assertEqual(entry.effective_date, MID_YEAR)
        self.assertEqual(report.paid, 1)

    async def test_the_run_is_committed_once(self):
        self._directory({"ann": _profile(), "bob": _profile()})

        await self.service.run_weekly_accrual(self.session, today=MID_YEAR)

        self.session.commit.assert_awaited_once()

    async def test_a_second_run_on_the_same_day_pays_nothing(self):
        """Not by looking for its own row: the target formula already counts
        what it granted, so the difference is zero. The unique index is only
        the backstop for two runs at once."""
        self._directory({"ann": _profile()})
        self.repository.sum_weekly_accrual.return_value = Decimal("41.54")

        report = await self.service.run_weekly_accrual(self.session, today=MID_YEAR)

        self.assertEqual(self._written(), [])
        self.assertEqual(report.paid, 0)

    async def test_someone_on_a_zero_entitlement_is_still_walked_over(self):
        """An L1 accrues nothing today, and filtering them out would mean that
        the day L1 stops being zero, the people filtered out get nothing and
        nothing reports it."""
        self._directory({"ann": _profile(level="L1", annual_hours=0)})

        report = await self.service.run_weekly_accrual(self.session, today=MID_YEAR)

        self.assertEqual(self._written(), [])
        self.assertEqual(report.considered, 1)
        self.assertEqual(report.skipped_left, ())

    async def test_a_level_change_splits_the_year_for_the_person_it_belongs_to(self):
        self._directory({"ann": _profile()})
        self.repository.latest_level_change_date.return_value = datetime.date(
            2026, 7, 1
        )
        self.repository.sum_weekly_accrual.side_effect = [
            Decimal("0.00"),
            Decimal("0.00"),
        ]

        await self.service.run_weekly_accrual(self.session, today=MID_YEAR)

        self.assertEqual(self._written()[0].hours, Decimal("1.54"))
        bounded = self.repository.latest_level_change_date.await_args.kwargs
        self.assertEqual(bounded["on_or_before"], MID_YEAR)

    async def test_somebody_who_has_left_is_skipped(self):
        self._directory({"ann": _profile(leave_date="2026-05-31")})

        report = await self.service.run_weekly_accrual(self.session, today=MID_YEAR)

        self.assertEqual(self._written(), [])
        self.assertEqual(report.skipped_left, ("ann",))

    async def test_a_disabled_account_is_treated_as_gone(self):
        """Azure does not always carry a leave date -- one of the five China
        full-timers is disabled without one. Without this they accrue for
        ever."""
        self._directory({"ann": _profile(account_enabled=False)})

        report = await self.service.run_weekly_accrual(self.session, today=MID_YEAR)

        self.assertEqual(self._written(), [])
        self.assertEqual(report.skipped_left, ("ann",))

    async def test_a_leave_date_still_in_the_future_is_not_gone_yet(self):
        self._directory({"ann": _profile(leave_date="2026-12-31")})

        report = await self.service.run_weekly_accrual(self.session, today=MID_YEAR)

        self.assertEqual(len(self._written()), 1)
        self.assertEqual(report.skipped_left, ())

    async def test_a_missing_hire_date_is_reported_rather_than_guessed(self):
        """Accrual starts at the hire date. Assuming 1 January would overpay
        somebody hired in June, and nothing would say so."""
        self._directory({"ann": _profile(hire_date=None)})

        report = await self.service.run_weekly_accrual(self.session, today=MID_YEAR)

        self.assertEqual(self._written(), [])
        self.assertEqual(report.skipped_no_hire_date, ("ann",))

    async def test_whoever_has_no_purrf_account_is_reported(self):
        """A ledger row needs a user_id. Being unmatched means being unpaid,
        and an unpaid person is invisible in their own balance."""
        self._directory(
            {"ann": _profile()},
            ResolvedParticipants(by_ldap={}, unresolved=("ann",), not_internal=()),
        )

        report = await self.service.run_weekly_accrual(self.session, today=MID_YEAR)

        self.assertEqual(report.unresolved, ("ann",))
        self.assertEqual(self._written(), [])

    async def test_an_empty_directory_is_a_warning_not_a_quiet_success(self):
        """The profiles come from a cache the nightly sync rebuilds. If it is
        empty the job would otherwise report a clean run over nobody."""
        self._directory({})

        report = await self.service.run_weekly_accrual(self.session, today=MID_YEAR)

        self.assertEqual(report.considered, 0)
        self.logger.warning.assert_called()

    async def test_an_unreadable_profile_skips_that_person_only(self):
        self._directory({"ann": "{not json", "bob": _profile()})

        report = await self.service.run_weekly_accrual(self.session, today=MID_YEAR)

        self.assertEqual([entry.user_id for entry in self._written()], [11])
        self.assertEqual(report.unreadable, ("ann",))


class TestAnnualClose(LeaveEngineServiceTest):
    async def test_the_closing_year_is_the_one_that_just_ended(self):
        self._directory({"ann": _profile()})
        self.repository.sum_weekly_accrual.return_value = Decimal("78.46")

        report = await self.service.run_annual_close(self.session, today=NEW_YEAR)

        self.assertEqual(report.closing_year, 2026)

    async def test_the_settlement_is_dated_to_december_31st(self):
        """Dated 1 January it would read as the new year opening by paying out
        last year's remainder, and it would fall inside the new year's total."""
        self._directory({"ann": _profile()})
        self.repository.sum_weekly_accrual.return_value = Decimal("78.46")

        await self.service.run_annual_close(self.session, today=NEW_YEAR)

        settlement = self._written()[0]
        self.assertEqual(settlement.entry_type, LeaveEntryType.WEEKLY_ACCRUAL)
        self.assertEqual(settlement.hours, Decimal("1.54"))
        self.assertEqual(settlement.effective_date, datetime.date(2026, 12, 31))

    async def test_a_late_rerun_still_dates_the_settlement_to_december_31st(self):
        self._directory({"ann": _profile()})
        self.repository.sum_weekly_accrual.return_value = Decimal("78.46")

        await self.service.run_annual_close(
            self.session, today=datetime.date(2027, 1, 4)
        )

        self.assertEqual(self._written()[0].effective_date, datetime.date(2026, 12, 31))

    async def test_the_ceiling_is_applied_after_the_settlement_not_before(self):
        """The hours the settlement just paid have to be subject to the same
        ceiling. Trimming first would let them through it unchecked."""
        self._directory({"ann": _profile()})
        self.repository.sum_weekly_accrual.return_value = Decimal("78.46")
        self.repository.balance.return_value = Decimal("80.00")

        with patch("backend.leave.leave_engine_service.MAX_CARRYOVER_HOURS", 40):
            await self.service.run_annual_close(self.session, today=NEW_YEAR)

        kinds = [entry.entry_type for entry in self._written()]
        self.assertEqual(
            kinds,
            [LeaveEntryType.WEEKLY_ACCRUAL, LeaveEntryType.CARRYOVER_FORFEIT],
        )
        self.assertEqual(self.repository.balance.await_args_list[0].args[1:], (10,))

    async def test_no_ceiling_means_no_forfeit_but_the_settlement_still_runs(self):
        self._directory({"ann": _profile()})
        self.repository.sum_weekly_accrual.return_value = Decimal("78.46")
        self.repository.balance.return_value = Decimal("500.00")

        report = await self.service.run_annual_close(self.session, today=NEW_YEAR)

        self.assertEqual(report.forfeited, 0)
        self.assertEqual(report.settled, 1)

    async def test_a_forfeit_is_written_as_a_negative_dated_december_31st(self):
        self._directory({"ann": _profile()})
        self.repository.sum_weekly_accrual.return_value = Decimal("80.00")
        self.repository.balance.return_value = Decimal("60.00")

        with patch("backend.leave.leave_engine_service.MAX_CARRYOVER_HOURS", 40):
            report = await self.service.run_annual_close(self.session, today=NEW_YEAR)

        forfeit = self._written()[0]
        self.assertEqual(forfeit.entry_type, LeaveEntryType.CARRYOVER_FORFEIT)
        self.assertEqual(forfeit.hours, Decimal("-20.00"))
        self.assertEqual(forfeit.effective_date, datetime.date(2026, 12, 31))
        self.assertEqual(report.forfeited, 1)

    async def test_a_negative_balance_carries_into_the_new_year_untouched(self):
        """An L1 is expected to sit in the red. Year end is not debt
        forgiveness, and it is not a moment to clamp it either."""
        self._directory({"ann": _profile(level="L1", annual_hours=0)})
        self.repository.balance.return_value = Decimal("-16.00")

        with patch("backend.leave.leave_engine_service.MAX_CARRYOVER_HOURS", 40):
            report = await self.service.run_annual_close(self.session, today=NEW_YEAR)

        self.assertEqual(self._written(), [])
        self.assertEqual(report.forfeited, 0)

    async def test_somebody_who_left_is_neither_settled_nor_trimmed(self):
        """Settling a leaver would pay them for the weeks after they left: the
        arithmetic has no leave date in it, so the loop has to hold that."""
        self._directory({"ann": _profile(leave_date="2026-05-31")})
        self.repository.sum_weekly_accrual.return_value = Decimal("20.00")

        report = await self.service.run_annual_close(self.session, today=NEW_YEAR)

        self.assertEqual(self._written(), [])
        self.assertEqual(report.skipped_left, ("ann",))

    async def test_a_level_change_is_read_as_of_the_closing_year(self):
        """A promotion in the new year must not split the year being closed."""
        self._directory({"ann": _profile()})

        await self.service.run_annual_close(self.session, today=NEW_YEAR)

        self.assertEqual(
            self.repository.latest_level_change_date.await_args.kwargs["on_or_before"],
            datetime.date(2026, 12, 31),
        )

    async def test_a_second_close_of_the_same_year_writes_nothing(self):
        self._directory({"ann": _profile()})
        self.repository.sum_weekly_accrual.return_value = Decimal("80.00")
        self.repository.balance.return_value = Decimal("40.00")

        with patch("backend.leave.leave_engine_service.MAX_CARRYOVER_HOURS", 40):
            report = await self.service.run_annual_close(self.session, today=NEW_YEAR)

        self.assertEqual(self._written(), [])
        self.assertEqual((report.settled, report.forfeited), (0, 0))


def _person(user_id, first, last, preferred=None):
    row = MagicMock()
    row.user_id = user_id
    row.first_name = first
    row.last_name = last
    row.preferred_name = preferred
    return row


class TestOverview(LeaveEngineServiceTest):
    """What an administrator is shown, and why it is built on the run itself.

    An overview assembled from its own query could disagree with what the job
    actually pays, and noticing that kind of gap is the whole point of the page.
    """

    async def test_it_lists_the_people_this_run_would_pay(self):
        self._directory({"ann": _profile(), "bob": _profile()})
        self.users.get_all_by_ids.return_value = [
            _person(10, "Ann", "Employee"),
            _person(11, "Bob", "Report"),
        ]
        self.repository.balances_by_user_ids.return_value = {
            10: Decimal("72.00"),
            11: Decimal("8.00"),
        }

        overview = await self.service.overview(self.session)

        self.assertEqual([held.ldap for held in overview.people], ["ann", "bob"])
        self.assertEqual(
            [held.balance for held in overview.people],
            [Decimal("72.00"), Decimal("8.00")],
        )

    async def test_somebody_with_no_rows_holds_zero_rather_than_nothing(self):
        """The engine has them, so they have a balance -- it is zero."""
        self._directory({"ann": _profile()})
        self.users.get_all_by_ids.return_value = [_person(10, "Ann", "Employee")]
        self.repository.balances_by_user_ids.return_value = {}

        overview = await self.service.overview(self.session)

        self.assertEqual(overview.people[0].balance, Decimal("0.00"))

    async def test_it_carries_the_level_for_grouping(self):
        self._directory({"ann": _profile(level="L1", annual_hours=0)})
        self.users.get_all_by_ids.return_value = [_person(10, "Ann", "Employee")]
        self.repository.balances_by_user_ids.return_value = {}

        overview = await self.service.overview(self.session)

        self.assertEqual(overview.people[0].level, "L1")
        self.assertEqual(overview.people[0].annual_hours, 0)

    async def test_it_names_everybody_the_run_cannot_pay(self):
        """Somebody left out of every run is invisible in their own balance,
        which simply stays where it was. Each group names a different fix, so
        they stay apart rather than being counted together."""
        self._directory(
            {"ann": _profile(), "carol": _profile(hire_date=None)},
            resolved=ResolvedParticipants(
                by_ldap={"ann": 10}, unresolved=("dave",), not_internal=("erin",)
            ),
        )
        self.users.get_all_by_ids.return_value = [_person(10, "Ann", "Employee")]
        self.repository.balances_by_user_ids.return_value = {}

        overview = await self.service.overview(self.session)

        self.assertEqual(overview.excluded.no_hire_date, ("carol",))
        self.assertEqual(overview.excluded.unresolved, ("dave",))
        self.assertEqual(overview.excluded.not_internal, ("erin",))
        self.assertEqual(overview.profile_count, 2)

    async def test_names_are_ordered_here_not_by_the_database(self):
        """The production collation is byte-order, which files every
        capitalised name ahead of every lower-case one."""
        self._directory({"ann": _profile(), "bob": _profile()})
        self.users.get_all_by_ids.return_value = [
            _person(10, "zoe", "Adams"),
            _person(11, "Alice", "Brown"),
        ]
        self.repository.balances_by_user_ids.return_value = {}

        overview = await self.service.overview(self.session)

        self.assertEqual(
            [held.name for held in overview.people], ["Alice Brown", "zoe Adams"]
        )


if __name__ == "__main__":
    main()
