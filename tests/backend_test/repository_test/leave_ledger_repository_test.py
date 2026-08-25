"""Ledger reads the accrual engine depends on, and what the database refuses.

Every query here has a filter that is silent when it is wrong: a sum that
counts one type too many quietly changes everyone's entitlement, and a sum that
forgets the year stops the engine dead for a whole year. The database-level
cases at the bottom pin the guard against a cron paying twice.
"""

import datetime
from decimal import Decimal

from sqlalchemy.exc import IntegrityError

from backend.common.mentorship_enums import CommunicationMethod
from backend.common.leave_enums import LeaveEntryType
from backend.entity.leave_ledger_entity import LeaveLedgerEntity

# Imported for its side effect only: a ledger row's source_request_id points at
# leave_request, and SQLAlchemy cannot configure the ledger mapper until that
# table is in the registry. Production imports every entity at startup, so this
# only bites a test that names one of them.
from backend.entity.leave_request_entity import LeaveRequestEntity  # noqa: F401
from backend.entity.users_entity import UsersEntity
from backend.repository.leave_ledger_repository import LeaveLedgerRepository
from tests.backend_test.repository_test.base_repository_test_lib import (
    BaseRepositoryTestLib,
)


def _make_user() -> UsersEntity:
    return UsersEntity(
        first_name="U",
        last_name="Ser",
        timezone="Asia/Shanghai",
        timezone_updated_at=datetime.datetime.now(datetime.timezone.utc),
        communication_channel=CommunicationMethod.EMAIL,
        is_active=True,
        updated_timestamp=datetime.datetime.now(datetime.timezone.utc),
    )


class TestLeaveLedgerRepository(BaseRepositoryTestLib):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.repository = LeaveLedgerRepository()
        self.user = _make_user()
        self.other_user = _make_user()
        await self.insert_entities([self.user, self.other_user])

    def _entry(self, entry_type, hours, day, user=None):
        return LeaveLedgerEntity(
            user_id=(user or self.user).user_id,
            entry_type=entry_type,
            hours=Decimal(hours),
            effective_date=day,
        )

    async def test_the_engine_sum_counts_only_what_the_engine_granted(self):
        """An opening balance keyed in by hand sits alongside the accrual, not
        inside it. Counting it here would cancel out the hours it was meant to
        accompany, and nothing would report that."""
        await self.insert_entities([
            self._entry(
                LeaveEntryType.WEEKLY_ACCRUAL, "1.54", datetime.date(2026, 3, 1)
            ),
            self._entry(
                LeaveEntryType.MANUAL_ADJUSTMENT, "40.00", datetime.date(2026, 3, 2)
            ),
            self._entry(
                LeaveEntryType.EXCHANGE_CREDIT, "8.00", datetime.date(2026, 3, 3)
            ),
            self._entry(
                LeaveEntryType.LEAVE_DEDUCTION, "-8.00", datetime.date(2026, 3, 4)
            ),
            self._entry(
                LeaveEntryType.CARRYOVER_FORFEIT, "-20.00", datetime.date(2026, 3, 6)
            ),
            self._entry(LeaveEntryType.LEVEL_CHANGE, "0.00", datetime.date(2026, 3, 7)),
        ])

        granted = await self.repository.sum_weekly_accrual(
            self.session, self.user.user_id, 2026
        )

        self.assertEqual(granted, Decimal("1.54"))

    async def test_the_engine_sum_counts_only_the_year_asked_for(self):
        """The target resets every January while the ledger keeps accumulating.
        A sum across years compares this January's target against last year's
        whole entitlement, goes negative, and pays nothing for the entire year
        without raising anything."""
        await self.insert_entities([
            self._entry(
                LeaveEntryType.WEEKLY_ACCRUAL, "80.00", datetime.date(2026, 12, 31)
            ),
            self._entry(
                LeaveEntryType.WEEKLY_ACCRUAL, "1.54", datetime.date(2027, 1, 8)
            ),
        ])

        granted = await self.repository.sum_weekly_accrual(
            self.session, self.user.user_id, 2027
        )

        self.assertEqual(granted, Decimal("1.54"))

    async def test_the_engine_sum_is_per_person(self):
        await self.insert_entities([
            self._entry(
                LeaveEntryType.WEEKLY_ACCRUAL, "1.54", datetime.date(2026, 3, 1)
            ),
            self._entry(
                LeaveEntryType.WEEKLY_ACCRUAL,
                "80.00",
                datetime.date(2026, 3, 1),
                user=self.other_user,
            ),
        ])

        granted = await self.repository.sum_weekly_accrual(
            self.session, self.user.user_id, 2026
        )

        self.assertEqual(granted, Decimal("1.54"))

    async def test_an_empty_ledger_sums_to_zero_rather_than_none(self):
        """The arithmetic subtracts this from a target, so None would raise
        rather than pay a first week."""
        granted = await self.repository.sum_weekly_accrual(
            self.session, self.user.user_id, 2026
        )

        self.assertEqual(granted, Decimal("0.00"))

    async def test_the_engine_sum_can_stop_at_a_level_change(self):
        """A promotion splits the year: what came before it stands as recorded,
        and the weeks after are computed at the new entitlement. The cut is
        strictly before the change date -- a row dated on the day of the change
        belongs to the new level."""
        await self.insert_entities([
            self._entry(
                LeaveEntryType.WEEKLY_ACCRUAL, "20.00", datetime.date(2026, 6, 30)
            ),
            self._entry(
                LeaveEntryType.WEEKLY_ACCRUAL, "1.54", datetime.date(2026, 7, 1)
            ),
            self._entry(
                LeaveEntryType.WEEKLY_ACCRUAL, "1.54", datetime.date(2026, 7, 8)
            ),
        ])

        granted_before = await self.repository.sum_weekly_accrual(
            self.session, self.user.user_id, 2026, before=datetime.date(2026, 7, 1)
        )

        self.assertEqual(granted_before, Decimal("20.00"))

    async def test_a_balance_is_every_row_regardless_of_type(self):
        """There is no balance column and no second source of truth, so this
        sum must not filter by type at all -- which is why a level change
        carries no hours."""
        await self.insert_entities([
            self._entry(
                LeaveEntryType.WEEKLY_ACCRUAL, "80.00", datetime.date(2026, 12, 31)
            ),
            self._entry(
                LeaveEntryType.LEAVE_DEDUCTION, "-8.00", datetime.date(2026, 5, 6)
            ),
            self._entry(
                LeaveEntryType.MANUAL_ADJUSTMENT, "40.00", datetime.date(2026, 1, 2)
            ),
            self._entry(
                LeaveEntryType.CARRYOVER_FORFEIT, "-20.00", datetime.date(2025, 12, 31)
            ),
            self._entry(LeaveEntryType.LEVEL_CHANGE, "0.00", datetime.date(2026, 7, 1)),
        ])

        balance = await self.repository.balance(self.session, self.user.user_id)

        self.assertEqual(balance, Decimal("92.00"))

    async def test_a_balance_can_be_asked_for_as_it_stood_on_a_date(self):
        """What the carryover trim cuts is the overshoot a year ended with, so
        it has to ask what the balance was on 31 December. Two rows can already
        sit between that and the balance now by the time the close runs: the
        new year's first weekly accrual, and leave approved in December for a
        January date."""
        await self.insert_entities([
            self._entry(
                LeaveEntryType.WEEKLY_ACCRUAL, "80.00", datetime.date(2026, 12, 31)
            ),
            self._entry(
                LeaveEntryType.WEEKLY_ACCRUAL, "1.54", datetime.date(2027, 1, 1)
            ),
            self._entry(
                LeaveEntryType.LEAVE_DEDUCTION, "-8.00", datetime.date(2027, 1, 4)
            ),
        ])

        at_year_end = await self.repository.balance(
            self.session, self.user.user_id, on_or_before=datetime.date(2026, 12, 31)
        )
        now = await self.repository.balance(self.session, self.user.user_id)

        self.assertEqual(at_year_end, Decimal("80.00"))
        self.assertEqual(now, Decimal("73.54"))

    async def test_only_deductions_inside_the_year_count_as_taken(self):
        """An exchange credit and an opening balance are not leave taken, and a
        figure summed across years would say somebody spent this year what they
        spent over their whole employment."""
        await self.insert_entities([
            self._entry(
                LeaveEntryType.LEAVE_DEDUCTION, "-8.00", datetime.date(2026, 5, 6)
            ),
            self._entry(
                LeaveEntryType.LEAVE_DEDUCTION, "-16.00", datetime.date(2026, 7, 1)
            ),
            self._entry(
                LeaveEntryType.LEAVE_DEDUCTION, "-40.00", datetime.date(2025, 3, 2)
            ),
            self._entry(
                LeaveEntryType.EXCHANGE_CREDIT, "8.00", datetime.date(2026, 6, 1)
            ),
            self._entry(
                LeaveEntryType.MANUAL_ADJUSTMENT, "-8.00", datetime.date(2026, 2, 1)
            ),
        ])

        taken = await self.repository.sum_deductions_for_year(
            self.session, self.user.user_id, 2026
        )

        self.assertEqual(taken, Decimal("-24.00"))

    async def test_a_year_with_nothing_taken_is_zero_not_none(self):
        taken = await self.repository.sum_deductions_for_year(
            self.session, self.user.user_id, 2026
        )

        self.assertEqual(taken, Decimal("0.00"))

    async def test_balances_come_back_per_person_in_one_read(self):
        """An approver's queue needs a balance for everybody in it, and one
        query per row would grow with the queue."""
        await self.insert_entities([
            self._entry(
                LeaveEntryType.WEEKLY_ACCRUAL, "80.00", datetime.date(2026, 3, 1)
            ),
            self._entry(
                LeaveEntryType.LEAVE_DEDUCTION, "-8.00", datetime.date(2026, 5, 6)
            ),
            self._entry(
                LeaveEntryType.WEEKLY_ACCRUAL,
                "40.00",
                datetime.date(2026, 3, 1),
                user=self.other_user,
            ),
        ])

        balances = await self.repository.balances_by_user_ids(
            self.session, [self.user.user_id, self.other_user.user_id]
        )

        self.assertEqual(balances[self.user.user_id], Decimal("72.00"))
        self.assertEqual(balances[self.other_user.user_id], Decimal("40.00"))

    async def test_a_person_with_no_rows_is_left_out_rather_than_guessed_at(self):
        """Absent and zero are different questions, and only the caller knows
        which answer it wants."""
        balances = await self.repository.balances_by_user_ids(
            self.session, [self.user.user_id]
        )

        self.assertEqual(balances, {})

    async def test_asking_for_nobody_does_not_query(self):
        balances = await self.repository.balances_by_user_ids(self.session, [])

        self.assertEqual(balances, {})

    async def test_a_balance_may_be_negative(self):
        """An L1 has no entitlement and may still take paid leave, so sitting
        in the red is expected rather than a fault to clamp away."""
        await self.insert_entities([
            self._entry(
                LeaveEntryType.LEAVE_DEDUCTION, "-16.00", datetime.date(2026, 5, 6)
            )
        ])

        balance = await self.repository.balance(self.session, self.user.user_id)

        self.assertEqual(balance, Decimal("-16.00"))

    async def test_the_level_change_date_is_the_most_recent_one(self):
        await self.insert_entities([
            self._entry(LeaveEntryType.LEVEL_CHANGE, "0.00", datetime.date(2026, 3, 2)),
            self._entry(LeaveEntryType.LEVEL_CHANGE, "0.00", datetime.date(2026, 7, 1)),
        ])

        level_since = await self.repository.latest_level_change_date(
            self.session, self.user.user_id
        )

        self.assertEqual(level_since, datetime.date(2026, 7, 1))

    async def test_the_level_change_date_can_be_bounded(self):
        """The annual job closes out last year, so it must not see a change
        that happened after that year ended -- it would split the closing year
        at a date outside it and pay the wrong proportion."""
        await self.insert_entities([
            self._entry(LeaveEntryType.LEVEL_CHANGE, "0.00", datetime.date(2026, 7, 1)),
            self._entry(LeaveEntryType.LEVEL_CHANGE, "0.00", datetime.date(2027, 2, 3)),
        ])

        level_since = await self.repository.latest_level_change_date(
            self.session, self.user.user_id, on_or_before=datetime.date(2026, 12, 31)
        )

        self.assertEqual(level_since, datetime.date(2026, 7, 1))

    async def test_a_bound_on_the_change_date_is_inclusive(self):
        await self.insert_entities([
            self._entry(LeaveEntryType.LEVEL_CHANGE, "0.00", datetime.date(2026, 7, 1))
        ])

        level_since = await self.repository.latest_level_change_date(
            self.session, self.user.user_id, on_or_before=datetime.date(2026, 7, 1)
        )

        self.assertEqual(level_since, datetime.date(2026, 7, 1))

    async def test_no_level_change_reads_as_none(self):
        """Almost everybody. The arithmetic treats None as "the whole year at
        the current entitlement", which is the plain formula."""
        await self.insert_entities([
            self._entry(
                LeaveEntryType.WEEKLY_ACCRUAL, "1.54", datetime.date(2026, 3, 1)
            )
        ])

        level_since = await self.repository.latest_level_change_date(
            self.session, self.user.user_id
        )

        self.assertIsNone(level_since)

    async def test_entries_are_written_without_being_committed(self):
        """The caller owns the transaction: a job writes for many people and
        either the whole run lands or none of it does."""
        await self.repository.add_entries(
            self.session,
            [
                self._entry(
                    LeaveEntryType.WEEKLY_ACCRUAL, "1.54", datetime.date(2026, 3, 1)
                )
            ],
        )

        self.assertEqual(
            await self.repository.sum_weekly_accrual(
                self.session, self.user.user_id, 2026
            ),
            Decimal("1.54"),
        )

    async def test_the_same_accrual_cannot_be_written_twice_for_one_day(self):
        """The guard behind "a retried pod does not double-grant". It is the
        partial unique index doing this, so it has to be checked against a real
        database rather than asserted on the model."""
        await self.repository.add_entries(
            self.session,
            [
                self._entry(
                    LeaveEntryType.WEEKLY_ACCRUAL, "1.54", datetime.date(2026, 3, 1)
                )
            ],
        )

        with self.assertRaises(IntegrityError):
            await self.repository.add_entries(
                self.session,
                [
                    self._entry(
                        LeaveEntryType.WEEKLY_ACCRUAL, "1.54", datetime.date(2026, 3, 1)
                    )
                ],
            )

    async def test_a_level_may_change_twice_in_one_day(self):
        """Deliberately outside that index. A level raised and put back inside
        one day is two real events; rejecting the second would drop an event
        rather than deduplicate a payment."""
        await self.repository.add_entries(
            self.session,
            [
                self._entry(
                    LeaveEntryType.LEVEL_CHANGE, "0.00", datetime.date(2026, 7, 1)
                ),
                self._entry(
                    LeaveEntryType.LEVEL_CHANGE, "0.00", datetime.date(2026, 7, 1)
                ),
            ],
        )

        self.assertEqual(
            await self.repository.latest_level_change_date(
                self.session, self.user.user_id
            ),
            datetime.date(2026, 7, 1),
        )


if __name__ == "__main__":
    import unittest

    unittest.main()
