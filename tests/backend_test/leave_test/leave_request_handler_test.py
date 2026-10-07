"""What a leave request checks and does, as an approval."""

import datetime
import unittest
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from backend.common.approval_enums import ApprovalRequestStatus
from backend.common.leave_enums import (
    LeaveEntryType,
    LeaveEvent,
    LeaveRequestStatus,
    LeaveRequestType,
)
from backend.entity.approval_request_entity import ApprovalRequestEntity
from backend.leave.leave_request_handler import LeaveRequestHandler
from backend.leave.leave_workdays import request_hours

LEAVE_ID = 77
EMPLOYEE = 12
MANAGER = 40
# Pinned, so the "already started" check does not depend on the day the test
# runs; the leave below is three working days after it (the weekend is Sunday
# and Monday).
TODAY = datetime.date(2026, 10, 7)
START = datetime.date(2026, 11, 3)
END = datetime.date(2026, 11, 5)


def _holiday(day, exchangeable=False):
    return SimpleNamespace(date=day, is_exchangeable=exchangeable)


def _leave(*, leave_type=LeaveRequestType.PAID, start=START, end=END, hours=None):
    return SimpleNamespace(
        leave_request_id=LEAVE_ID,
        user_id=EMPLOYEE,
        type=leave_type,
        start_date=start,
        end_date=end,
        start_time=None,
        end_time=None,
        hours=(
            hours
            if hours is not None
            else request_hours(leave_type, start, end, None, None, frozenset())
        ),
        status=LeaveRequestStatus.PENDING,
        approver_user_id=MANAGER,
        is_overdraft=False,
    )


def _request():
    return ApprovalRequestEntity(
        action="leave_approval",
        target_type="leave_request",
        target_id=str(LEAVE_ID),
        payload={},
        raised_by=EMPLOYEE,
        reviewer_id=MANAGER,
    )


class LeaveRequestHandlerTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.session = MagicMock()
        self.leave = _leave()
        self.requests = MagicMock()
        self.requests.get_by_id = AsyncMock(side_effect=lambda *a, **k: self.leave)
        self.requests.sum_pending_paid_hours = AsyncMock(return_value=Decimal("0"))
        self.ledger = MagicMock()
        self.ledger.balance = AsyncMock(return_value=Decimal("100"))
        self.ledger.add_entries = AsyncMock()
        self.holidays = MagicMock()
        # A calendar is entered for the year, with no holiday in the leave.
        self.holidays.list_by_year = AsyncMock(
            return_value=[_holiday(datetime.date(2026, 10, 1))]
        )
        self.users = MagicMock()
        self.employee = SimpleNamespace(
            user_id=EMPLOYEE,
            is_active=True,
            first_name="Lin",
            last_name="Wei",
            preferred_name=None,
        )
        self.users.get_user_by_user_id = AsyncMock(
            side_effect=lambda session, user_id: self.employee
        )
        self.handler = LeaveRequestHandler(
            self.requests, self.ledger, self.holidays, self.users
        )
        patcher = patch(
            "backend.leave.leave_request_handler.business_today", return_value=TODAY
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_declares_an_assigned_reviewer_that_cannot_be_changed(self):
        self.assertEqual(self.handler.action, "leave_approval")
        self.assertEqual(self.handler.target_type, "leave_request")
        self.assertEqual(self.handler.subject_type, "leave_request")
        self.assertIsNone(self.handler.review_permission)
        self.assertFalse(self.handler.raiser_may_reassign)
        self.assertEqual(self.handler.raised_event, LeaveEvent.REQUEST_SUBMITTED)
        self.assertEqual(self.handler.decided_event, LeaveEvent.REQUEST_DECIDED)
        self.assertEqual(self.handler.subject_id(_request()), LEAVE_ID)

    async def test_the_reviewer_is_the_manager_stored_on_the_request(self):
        reviewer = await self.handler.assign_reviewer(
            self.session, raised_by=EMPLOYEE, target_id=str(LEAVE_ID), payload={}
        )
        self.assertEqual(reviewer, MANAGER)

    async def test_only_the_owner_raises_it_and_only_while_pending(self):
        await self.handler.check_raise(
            self.session, raised_by=EMPLOYEE, target_id=str(LEAVE_ID), payload={}
        )
        with self.assertRaises(PermissionError):
            await self.handler.check_raise(
                self.session, raised_by=MANAGER, target_id=str(LEAVE_ID), payload={}
            )
        self.leave.status = LeaveRequestStatus.APPROVED
        with self.assertRaises(ValueError):
            await self.handler.check_raise(
                self.session, raised_by=EMPLOYEE, target_id=str(LEAVE_ID), payload={}
            )

    async def test_an_unknown_request_is_refused(self):
        self.leave = None
        with self.assertRaises(ValueError):
            await self.handler.assign_reviewer(
                self.session, raised_by=EMPLOYEE, target_id=str(LEAVE_ID), payload={}
            )

    async def test_events_carry_what_the_request_was_for(self):
        details = await self.handler.event_details(self.session, _request())
        self.assertEqual(details["employeeName"], "Lin Wei")
        self.assertEqual(details["leaveType"], "paid")
        self.assertEqual(details["startDate"], "2026-11-03")
        self.assertEqual(details["endDate"], "2026-11-05")
        self.assertEqual(details["hours"], f"{self.leave.hours:.2f}")

    async def test_nothing_stands_in_the_way_of_approving_it_as_filed(self):
        self.assertEqual(
            await self.handler.problems_at_approval(self.session, _request()), []
        )

    async def test_leave_that_has_started_cannot_be_approved(self):
        self.leave = _leave(
            start=TODAY - datetime.timedelta(days=1),
            end=TODAY + datetime.timedelta(days=1),
        )
        problems = await self.handler.problems_at_approval(self.session, _request())
        self.assertEqual(len(problems), 1)
        self.assertIn("started", problems[0])

    async def test_leave_starting_today_can_still_be_approved(self):
        # Filing for today is allowed, so approving it must be too.
        self.leave = _leave(start=TODAY, end=TODAY)
        self.assertEqual(
            await self.handler.problems_at_approval(self.session, _request()), []
        )

    async def test_a_holiday_entered_since_filing_stops_the_approval(self):
        self.holidays.list_by_year.return_value = [_holiday(START)]
        problems = await self.handler.problems_at_approval(self.session, _request())
        self.assertEqual(len(problems), 1)
        self.assertIn("company holidays entered since", problems[0])

    async def test_a_year_with_no_holidays_entered_stops_the_approval(self):
        self.holidays.list_by_year.return_value = []
        problems = await self.handler.problems_at_approval(self.session, _request())
        self.assertEqual(len(problems), 1)
        self.assertIn("have not been entered", problems[0])

    async def test_an_inactive_employee_stops_the_approval(self):
        self.employee.is_active = False
        problems = await self.handler.problems_at_approval(self.session, _request())
        self.assertEqual(len(problems), 1)
        self.assertIn("no longer active", problems[0])

    async def test_approving_writes_the_deduction_and_the_current_overdraft(self):
        # The balance was enough when filed and no longer is.
        self.ledger.balance.return_value = Decimal("10")
        self.requests.sum_pending_paid_hours.return_value = self.leave.hours

        await self.handler.execute(self.session, _request(), actor_id=MANAGER)

        self.assertIs(self.leave.status, LeaveRequestStatus.APPROVED)
        self.assertTrue(self.leave.is_overdraft)
        (entry,) = self.ledger.add_entries.await_args.args[1]
        self.assertEqual(entry.entry_type, LeaveEntryType.LEAVE_DEDUCTION)
        self.assertEqual(entry.hours, -self.leave.hours)
        self.assertEqual(entry.created_by, MANAGER)
        self.assertEqual(entry.source_request_id, LEAVE_ID)
        self.assertEqual(entry.effective_date, START)

    async def test_approving_sick_leave_writes_no_ledger_row(self):
        self.leave = _leave(leave_type=LeaveRequestType.SICK)

        await self.handler.execute(self.session, _request(), actor_id=MANAGER)

        self.assertIs(self.leave.status, LeaveRequestStatus.APPROVED)
        self.assertFalse(self.leave.is_overdraft)
        self.ledger.add_entries.assert_not_awaited()

    async def test_rejecting_and_withdrawing_close_it_as_such(self):
        await self.handler.revert(
            self.session, _request(), ApprovalRequestStatus.REJECTED
        )
        self.assertIs(self.leave.status, LeaveRequestStatus.REJECTED)

        self.leave = _leave()
        await self.handler.revert(
            self.session, _request(), ApprovalRequestStatus.WITHDRAWN
        )
        self.assertIs(self.leave.status, LeaveRequestStatus.WITHDRAWN)


if __name__ == "__main__":
    unittest.main()
