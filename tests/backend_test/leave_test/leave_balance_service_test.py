"""Employee leave balance reads and ledger entry query tests."""

import datetime
from decimal import Decimal
from unittest import IsolatedAsyncioTestCase, main
from unittest.mock import AsyncMock, MagicMock

from backend.leave.leave_balance_service import LeaveBalanceService


def _ledger_entry(
    leave_ledger_id=812,
    effective_date=datetime.date(2026, 3, 1),
    user_id=1,
    entry_type="ACCRUAL",
    hours=Decimal("8.00"),
    note="Monthly Accrual",
):
    """Helper to construct a mock leave ledger entry entity."""
    entry = MagicMock()
    entry.leave_ledger_id = leave_ledger_id
    entry.user_id = user_id
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
        self.repository.count_entries = AsyncMock(return_value=0)

        self.users_repository = MagicMock()
        self.users_repository.get_all_by_ids = AsyncMock(return_value=[])
        self.user_emails_repository = MagicMock()
        self.user_emails_repository.get_emails_by_user_ids = AsyncMock(return_value={})

        self.session = MagicMock()
        self.session.commit = AsyncMock()

        self.service = LeaveBalanceService(
            logger=self.logger,
            leave_ledger_repository=self.repository,
            users_repository=self.users_repository,
            user_emails_repository=self.user_emails_repository,
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

    async def test_user_with_no_ledger_history_returns_zero_balance_and_empty_list(
        self,
    ):
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

    async def test_invalid_user_id_raises_value_error_without_accessing_repository(
        self,
    ):
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

    async def test_list_ledger_paginates_and_resolves_names_and_ldaps(self):
        """Verify list_ledger queries entries with pagination, total count, and resolves names and ldaps correctly."""
        entry1 = _ledger_entry(
            leave_ledger_id=812,
            effective_date=datetime.date(2026, 7, 1),
            user_id=44,
            entry_type="level_change",
            hours=Decimal("0.00"),
            note="L1 -> L3",
        )
        entry2 = _ledger_entry(
            leave_ledger_id=799,
            effective_date=datetime.date(2026, 5, 6),
            user_id=51,
            entry_type="leave_deduction",
            hours=Decimal("-8.00"),
            note=None,
        )

        self.repository.list_entries.return_value = [entry1, entry2]
        self.repository.count_entries.return_value = 347

        self.users_repository.get_all_by_ids.return_value = [
            MagicMock(
                user_id=44, first_name="Wen", last_name="Zhang", preferred_name=None
            ),
            MagicMock(user_id=51, first_name="Li", last_name="Si", preferred_name=None),
        ]

        self.user_emails_repository.get_emails_by_user_ids.return_value = {
            44: ["wen.zhang@circlecat.org"],
            51: ["li.si@circlecat.org"],
        }

        page_dto = await self.service.list_ledger(
            self.session, user_id=None, page=1, page_size=50
        )

        self.repository.list_entries.assert_awaited_once_with(
            self.session, None, limit=50, offset=0
        )
        self.repository.count_entries.assert_awaited_once_with(self.session, None)

        self.assertEqual(page_dto.page, 1)
        self.assertEqual(page_dto.page_size, 50)
        self.assertEqual(page_dto.total_entries, 347)
        self.assertEqual(len(page_dto.entries), 2)

        row1 = page_dto.entries[0]
        self.assertEqual(row1.leave_ledger_id, 812)
        self.assertEqual(row1.effective_date, "2026-07-01")
        self.assertEqual(row1.user_id, 44)
        self.assertEqual(row1.name, "Wen Zhang")
        self.assertEqual(row1.ldap, "wen.zhang")
        self.assertEqual(row1.entry_type, "level_change")
        self.assertEqual(row1.hours, "0.00")
        self.assertEqual(row1.note, "L1 -> L3")

        row2 = page_dto.entries[1]
        self.assertEqual(row2.leave_ledger_id, 799)
        self.assertEqual(row2.effective_date, "2026-05-06")
        self.assertEqual(row2.user_id, 51)
        self.assertEqual(row2.name, "Li Si")
        self.assertEqual(row2.ldap, "li.si")
        self.assertEqual(row2.entry_type, "leave_deduction")
        self.assertEqual(row2.hours, "-8.00")
        self.assertIsNone(row2.note)

    async def test_list_ledger_only_resolves_users_on_that_page(self):
        """Verify user details are fetched ONLY for user_ids appearing on the requested page."""
        entry = _ledger_entry(user_id=99)
        self.repository.list_entries.return_value = [entry]
        self.repository.count_entries.return_value = 100

        self.users_repository.get_all_by_ids.return_value = [
            MagicMock(
                user_id=99, first_name="Ann", last_name="Lee", preferred_name=None
            )
        ]
        self.user_emails_repository.get_emails_by_user_ids.return_value = {
            99: ["ann.lee@circlecat.org"]
        }

        await self.service.list_ledger(self.session, user_id=10, page=2, page_size=10)

        self.repository.list_entries.assert_awaited_once_with(
            self.session, 10, limit=10, offset=10
        )

        self.users_repository.get_all_by_ids.assert_awaited_once_with(
            self.session, [99]
        )
        self.user_emails_repository.get_emails_by_user_ids.assert_awaited_once_with(
            self.session, [99]
        )


if __name__ == "__main__":
    main()
