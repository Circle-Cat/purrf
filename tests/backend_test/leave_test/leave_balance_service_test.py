"""Employee leave balance reads and ledger entry query tests."""

import datetime
from decimal import Decimal
from unittest import IsolatedAsyncioTestCase, main
from unittest.mock import AsyncMock, MagicMock

from backend.leave.leave_balance_service import LeaveBalanceService


def _ledger_entry(
    effective_date=datetime.date(2026, 3, 1),
    entry_type="ACCRUAL",
    hours=Decimal("8.00"),
    note="Monthly Accrual",
):
    """Helper to construct a mock leave ledger entry entity."""
    entry = MagicMock()
    entry.effective_date = effective_date
    entry.entry_type = entry_type
    entry.hours = hours
    entry.note = note
    return entry


class LeaveBalanceServiceTest(IsolatedAsyncioTestCase):
    def setUp(self):
        self.logger = MagicMock()
        self.repository = MagicMock()
        self.repository.balance = AsyncMock(return_value=Decimal("80.00"))
        self.repository.list_entries = AsyncMock(return_value=[])
        self.session = MagicMock()
        self.session.commit = AsyncMock()

        self.service = LeaveBalanceService(
            logger=self.logger,
            leave_ledger_repository=self.repository,
        )

    async def test_get_leave_balance_returns_formatted_dto_with_ledger_entries(self):
        """Fetch total balance and complete ledger history, verifying numeric formatting and structure."""
        self.repository.balance.return_value = Decimal("80.00")
        self.repository.list_entries.return_value = [
            _ledger_entry(
                effective_date=datetime.date(2026, 3, 1),
                entry_type="ACCRUAL",
                hours=Decimal("8.00"),
                note="Monthly Accrual",
            )
        ]

        balance_dto = await self.service.get_leave_balance(self.session, user_id=1)

        self.repository.balance.assert_awaited_once_with(self.session, 1)
        self.repository.list_entries.assert_awaited_once_with(self.session, 1)

        self.assertEqual(balance_dto.balanceHours, "80.00")
        self.assertEqual(len(balance_dto.entries), 1)
        self.assertEqual(balance_dto.entries[0].effectiveDate, "2026-03-01")
        self.assertEqual(balance_dto.entries[0].entryType, "ACCRUAL")
        self.assertEqual(balance_dto.entries[0].hours, "8.00")
        self.assertEqual(balance_dto.entries[0].note, "Monthly Accrual")

    async def test_user_with_no_ledger_history_returns_zero_balance_and_empty_list(self):
        """A user without any ledger records must yield 0.00 hours and an empty entries list."""
        self.repository.balance.return_value = Decimal("0.00")
        self.repository.list_entries.return_value = []

        balance_dto = await self.service.get_leave_balance(self.session, user_id=99)

        self.assertEqual(balance_dto.balanceHours, "0.00")
        self.assertEqual(balance_dto.entries, [])

    async def test_get_leave_balance_is_read_only_and_does_not_commit_session(self):
        """Read-only queries must strictly avoid issuing database commits."""
        await self.service.get_leave_balance(self.session, user_id=1)

        self.session.commit.assert_not_awaited()

    async def test_numeric_rounding_and_precision_formatting_boundaries(self):
        """Verify multi-decimal floats or integer Decimals correctly format to two decimal places."""
        self.repository.balance.return_value = Decimal("37.5")
        self.repository.list_entries.return_value = [
            _ledger_entry(hours=Decimal("7.666")),
            _ledger_entry(hours=Decimal("0")),
        ]

        balance_dto = await self.service.get_leave_balance(self.session, user_id=1)

        self.assertEqual(balance_dto.balanceHours, "37.50")
        self.assertEqual(balance_dto.entries[0].hours, "7.67")
        self.assertEqual(balance_dto.entries[1].hours, "0.00")

    async def test_invalid_user_id_raises_value_error_without_accessing_repository(self):
        """Passing a non-positive or invalid user_id must raise ValueError directly."""
        with self.assertRaises(ValueError):
            await self.service.get_leave_balance(self.session, user_id=-1)

        self.repository.balance.assert_not_awaited()
        self.repository.list_entries.assert_not_awaited()

    async def test_repository_exception_propagates_without_session_commit(self):
        """Database connection or query errors from repository must bubble up safely."""
        self.repository.balance.side_effect = RuntimeError("Database connection lost")

        with self.assertRaises(RuntimeError):
            await self.service.get_leave_balance(self.session, user_id=1)

        self.session.commit.assert_not_awaited()


if __name__ == "__main__":
    main()