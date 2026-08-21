"""Request reads the submission checks depend on.

The overlap query is the one that has to be exactly right: it is what stops the
same day being deducted twice, and by the time a duplicate is noticed both
deductions are already ledger rows that cannot be edited.
"""

import datetime
from decimal import Decimal

from backend.common.leave_enums import LeaveRequestStatus, LeaveRequestType
from backend.common.mentorship_enums import CommunicationMethod
from backend.entity.leave_request_entity import LeaveRequestEntity
from backend.entity.users_entity import UsersEntity
from backend.repository.leave_request_repository import LeaveRequestRepository
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


class TestLeaveRequestRepository(BaseRepositoryTestLib):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.repository = LeaveRequestRepository()
        self.employee = _make_user()
        self.colleague = _make_user()
        self.manager = _make_user()
        await self.insert_entities([self.employee, self.colleague, self.manager])

    def _request(
        self,
        start,
        end,
        status=LeaveRequestStatus.PENDING,
        request_type=LeaveRequestType.PAID,
        hours="8.00",
        user=None,
    ):
        return LeaveRequestEntity(
            user_id=(user or self.employee).user_id,
            type=request_type,
            start_date=start,
            end_date=end,
            hours=Decimal(hours),
            status=status,
            approver_user_id=self.manager.user_id,
        )

    async def test_a_new_request_comes_back_with_an_id(self):
        request = await self.repository.add(
            self.session,
            self._request(datetime.date(2026, 8, 13), datetime.date(2026, 8, 13)),
        )

        self.assertIsNotNone(request.leave_request_id)

    async def test_a_pending_request_on_the_same_day_is_an_overlap(self):
        await self.insert_entities([
            self._request(datetime.date(2026, 8, 13), datetime.date(2026, 8, 15))
        ])

        clashes = await self.repository.list_overlapping(
            self.session,
            self.employee.user_id,
            datetime.date(2026, 8, 15),
            datetime.date(2026, 8, 17),
        )

        self.assertEqual(len(clashes), 1)

    async def test_an_approved_request_is_an_overlap_too(self):
        await self.insert_entities([
            self._request(
                datetime.date(2026, 8, 13),
                datetime.date(2026, 8, 13),
                status=LeaveRequestStatus.APPROVED,
            )
        ])

        clashes = await self.repository.list_overlapping(
            self.session,
            self.employee.user_id,
            datetime.date(2026, 8, 13),
            datetime.date(2026, 8, 13),
        )

        self.assertEqual(len(clashes), 1)

    async def test_a_request_that_went_nowhere_is_not_an_overlap(self):
        """Rejected and withdrawn requests deducted nothing, so those days are
        free again. Treating them as clashes would lock somebody out of a day
        they never took."""
        await self.insert_entities([
            self._request(
                datetime.date(2026, 8, 13),
                datetime.date(2026, 8, 13),
                status=LeaveRequestStatus.REJECTED,
            ),
            self._request(
                datetime.date(2026, 8, 13),
                datetime.date(2026, 8, 13),
                status=LeaveRequestStatus.WITHDRAWN,
            ),
        ])

        clashes = await self.repository.list_overlapping(
            self.session,
            self.employee.user_id,
            datetime.date(2026, 8, 13),
            datetime.date(2026, 8, 13),
        )

        self.assertEqual(clashes, [])

    async def test_a_request_ending_the_day_before_does_not_overlap(self):
        await self.insert_entities([
            self._request(datetime.date(2026, 8, 11), datetime.date(2026, 8, 12))
        ])

        clashes = await self.repository.list_overlapping(
            self.session,
            self.employee.user_id,
            datetime.date(2026, 8, 13),
            datetime.date(2026, 8, 14),
        )

        self.assertEqual(clashes, [])

    async def test_an_exchange_blocks_leave_over_the_same_day(self):
        """An exchange says "I am at work that day" and leave says the
        opposite. Both are requests, and the day cannot be both."""
        await self.insert_entities([
            self._request(
                datetime.date(2026, 10, 1),
                datetime.date(2026, 10, 1),
                request_type=LeaveRequestType.EXCHANGE,
            )
        ])

        clashes = await self.repository.list_overlapping(
            self.session,
            self.employee.user_id,
            datetime.date(2026, 9, 30),
            datetime.date(2026, 10, 2),
        )

        self.assertEqual(len(clashes), 1)

    async def test_somebody_elses_request_is_not_an_overlap(self):
        await self.insert_entities([
            self._request(
                datetime.date(2026, 8, 13),
                datetime.date(2026, 8, 13),
                user=self.colleague,
            )
        ])

        clashes = await self.repository.list_overlapping(
            self.session,
            self.employee.user_id,
            datetime.date(2026, 8, 13),
            datetime.date(2026, 8, 13),
        )

        self.assertEqual(clashes, [])

    async def test_pending_paid_hours_are_the_ones_held_back(self):
        """A pending request writes nothing to the ledger, so the balance has
        to hold its hours back separately or the same hours can be spent
        twice over."""
        await self.insert_entities([
            self._request(
                datetime.date(2026, 8, 13), datetime.date(2026, 8, 13), hours="8.00"
            ),
            self._request(
                datetime.date(2026, 8, 20), datetime.date(2026, 8, 20), hours="4.00"
            ),
        ])

        held = await self.repository.sum_pending_paid_hours(
            self.session, self.employee.user_id
        )

        self.assertEqual(held, Decimal("12.00"))

    async def test_sick_leave_holds_nothing_back(self):
        """It does not touch the balance at all, so reserving against it would
        take hours away from somebody who is owed them."""
        await self.insert_entities([
            self._request(
                datetime.date(2026, 8, 13),
                datetime.date(2026, 8, 13),
                request_type=LeaveRequestType.SICK,
                hours="8.00",
            )
        ])

        held = await self.repository.sum_pending_paid_hours(
            self.session, self.employee.user_id
        )

        self.assertEqual(held, Decimal("0.00"))

    async def test_an_approved_request_holds_nothing_back(self):
        """Once approved its hours are in the ledger. Counting them here as
        well would deduct them twice."""
        await self.insert_entities([
            self._request(
                datetime.date(2026, 8, 13),
                datetime.date(2026, 8, 13),
                status=LeaveRequestStatus.APPROVED,
            )
        ])

        held = await self.repository.sum_pending_paid_hours(
            self.session, self.employee.user_id
        )

        self.assertEqual(held, Decimal("0.00"))

    async def test_nothing_pending_holds_back_zero_not_none(self):
        held = await self.repository.sum_pending_paid_hours(
            self.session, self.employee.user_id
        )

        self.assertEqual(held, Decimal("0.00"))

    async def test_a_persons_own_requests_come_back_newest_first(self):
        await self.insert_entities([
            self._request(datetime.date(2026, 8, 13), datetime.date(2026, 8, 13)),
            self._request(datetime.date(2026, 9, 1), datetime.date(2026, 9, 1)),
            self._request(
                datetime.date(2026, 7, 1),
                datetime.date(2026, 7, 1),
                user=self.colleague,
            ),
        ])

        requests = await self.repository.list_for_user(
            self.session, self.employee.user_id
        )

        self.assertEqual(
            [request.start_date for request in requests],
            [datetime.date(2026, 9, 1), datetime.date(2026, 8, 13)],
        )

    async def test_an_approver_sees_only_what_is_waiting_on_them(self):
        other_manager = _make_user()
        await self.insert_entities([other_manager])
        waiting = self._request(datetime.date(2026, 8, 13), datetime.date(2026, 8, 13))
        decided = self._request(
            datetime.date(2026, 9, 1),
            datetime.date(2026, 9, 1),
            status=LeaveRequestStatus.APPROVED,
        )
        elsewhere = self._request(datetime.date(2026, 9, 2), datetime.date(2026, 9, 2))
        elsewhere.approver_user_id = other_manager.user_id
        await self.insert_entities([waiting, decided, elsewhere])

        queue = await self.repository.list_for_approver(
            self.session, self.manager.user_id, [LeaveRequestStatus.PENDING]
        )

        self.assertEqual(
            [request.leave_request_id for request in queue],
            [waiting.leave_request_id],
        )


if __name__ == "__main__":
    import unittest

    unittest.main()
