import datetime
import unittest
from decimal import Decimal

from backend.common.leave_enums import LeaveRequestStatus, LeaveRequestType
from backend.entity.leave_request_entity import LeaveRequestEntity


def _check_constraints():
    return {
        constraint.name: str(constraint.sqltext)
        for constraint in LeaveRequestEntity.__table__.constraints
        if constraint.__class__.__name__ == "CheckConstraint"
    }


class TestLeaveRequestEntity(unittest.TestCase):
    def test_request_carries_its_dates_hours_status_and_approver(self):
        request = LeaveRequestEntity(
            user_id=1,
            type=LeaveRequestType.PAID,
            start_date=datetime.date(2026, 3, 2),
            end_date=datetime.date(2026, 3, 3),
            hours=Decimal("16.00"),
            status=LeaveRequestStatus.PENDING,
            approver_user_id=2,
        )

        self.assertEqual(request.__tablename__, "leave_request")
        self.assertEqual(request.type, LeaveRequestType.PAID)
        self.assertEqual(request.hours, Decimal("16.00"))
        self.assertEqual(request.status, LeaveRequestStatus.PENDING)
        self.assertEqual(request.approver_user_id, 2)

    def test_an_approver_is_required(self):
        """Relaxing this to let someone with no manager submit would turn a
        blank HR field into unreviewed leave taking effect."""
        self.assertFalse(LeaveRequestEntity.__table__.c.approver_user_id.nullable)

    def test_times_are_only_allowed_within_a_single_day(self):
        constraint = _check_constraints()["ck_leave_request_times_only_on_a_single_day"]

        self.assertIn("start_date = end_date", constraint)
        self.assertIn("start_time IS NULL", constraint)
        self.assertIn("end_time IS NULL", constraint)

    def test_the_end_date_cannot_precede_the_start_date(self):
        self.assertIn(
            "end_date >= start_date",
            _check_constraints()["ck_leave_request_dates_ordered"],
        )

    def test_the_two_flags_default_to_false_in_the_database(self):
        """A row inserted by hand -- seeding, a backfill -- must not land with
        a NULL that later reads as "unknown"."""
        for name in ("is_overdraft", "is_late_notice"):
            column = LeaveRequestEntity.__table__.c[name]

            self.assertFalse(column.nullable)
            self.assertEqual(column.server_default.arg.text, "false")


class TestLeaveRequestEnums(unittest.TestCase):
    def test_there_is_no_unpaid_leave_type(self):
        self.assertEqual(
            {request_type.value for request_type in LeaveRequestType},
            {"paid", "sick", "exchange"},
        )

    def test_the_status_values_cover_the_whole_state_machine(self):
        """There is no state for cancelling an approved request: approval is
        the end of the line, and a value for it would read as a feature."""
        self.assertEqual(
            {status.value for status in LeaveRequestStatus},
            {"pending", "approved", "rejected", "withdrawn"},
        )


if __name__ == "__main__":
    unittest.main()
