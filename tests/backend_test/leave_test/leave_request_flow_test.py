"""A leave request end to end against a real database, through the shared
approval flow: file it, then approve, reject or withdraw, and read back the
request, its approval, the ledger, the events and who was told."""

import datetime
import json
import unittest
import uuid
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy import select

from backend.approval.approval_service import ApprovalService
from backend.common.approval_enums import ApprovalRequestStatus
from backend.common.exceptions import ConflictError
from backend.common.leave_enums import (
    LeaveEntryType,
    LeaveRequestType,
)
from backend.common.mentorship_enums import CommunicationMethod
from backend.entity.approval_request_entity import ApprovalRequestEntity
from backend.entity.event_entity import EventEntity
from backend.entity.leave_holiday_entity import LeaveHolidayEntity
from backend.entity.leave_ledger_entity import LeaveLedgerEntity
from backend.entity.notification_entity import NotificationEntity
from backend.entity.users_entity import UsersEntity
from backend.leave import notification_renderers  # noqa: F401 (registers)
from backend.leave import recipient_resolvers  # noqa: F401 (registers)
from backend.leave.leave_request_handler import LeaveRequestHandler
from backend.leave.leave_request_service import LeaveRequestService
from backend.repository.approval_request_repository import (
    ApprovalRequestRepository,
)
from backend.repository.leave_holiday_repository import LeaveHolidayRepository
from backend.repository.leave_ledger_repository import LeaveLedgerRepository
from backend.repository.leave_request_repository import LeaveRequestRepository
from backend.repository.user_permissions_repository import UserPermissionsRepository
from backend.repository.users_repository import UsersRepository
from tests.backend_test.repository_test.base_repository_test_lib import (
    BaseRepositoryTestLib,
)

# Pinned for both the service and the handler, so "has it started" never
# depends on the day the test runs. The weekend is Sunday and Monday, so the
# leave is three working days.
TODAY = datetime.date(2026, 10, 7)
START = datetime.date(2026, 11, 3)
END = datetime.date(2026, 11, 5)


def _user(first):
    return UsersEntity(
        first_name=first,
        last_name=uuid.uuid4().hex[:8],
        timezone="UTC",
        timezone_updated_at=datetime.datetime.now(datetime.timezone.utc),
        communication_channel=CommunicationMethod.EMAIL,
        is_active=True,
        is_super_admin=False,
        updated_timestamp=datetime.datetime.now(datetime.timezone.utc),
    )


class LeaveRequestFlowTest(BaseRepositoryTestLib):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.employee = _user("Lin")
        self.manager = _user("Mei")
        await self.insert_entities([self.employee, self.manager])
        await self.insert_entities([
            LeaveHolidayEntity(
                year=2026,
                date=datetime.date(2026, 12, 29),
                name="Flow test holiday",
                is_exchangeable=False,
            )
        ])

        # The Azure side: the employee's corporate address, their profile
        # naming a manager, and that manager's account.
        emails = MagicMock()
        emails.list_by_user_id = AsyncMock(
            return_value=[SimpleNamespace(email="lin@circlecat.org")]
        )
        emails.get_emails_by_user_ids = AsyncMock(return_value={})
        redis = MagicMock()
        redis.hgetall = MagicMock(
            return_value={"lin": json.dumps({"manager_ldap": "mei"})}
        )
        retry = MagicMock()
        retry.get_retry_on_transient = MagicMock(side_effect=lambda f, *a: f(*a))
        participants = MagicMock()
        participants.resolve = AsyncMock(
            return_value=SimpleNamespace(by_ldap={"mei": self.manager.user_id})
        )

        users = UsersRepository()
        requests = LeaveRequestRepository()
        ledger = LeaveLedgerRepository()
        holidays = LeaveHolidayRepository()
        approvals = ApprovalService(
            approval_request_repository=ApprovalRequestRepository(),
            user_permissions_repository=UserPermissionsRepository(),
            users_repository=users,
            logger=MagicMock(),
        )
        approvals.register(LeaveRequestHandler(requests, ledger, holidays, users))
        self.service = LeaveRequestService(
            logger=MagicMock(),
            leave_request_repository=requests,
            leave_ledger_repository=ledger,
            leave_holiday_repository=holidays,
            user_emails_repository=emails,
            users_repository=users,
            redis_client=redis,
            retry_utils=retry,
            participant_resolver=participants,
            approval_service=approvals,
        )
        for target in (
            "backend.leave.leave_request_service.business_today",
            "backend.leave.leave_request_handler.business_today",
        ):
            patcher = patch(target, return_value=TODAY)
            patcher.start()
            self.addCleanup(patcher.stop)

    async def _file(self, leave_type=LeaveRequestType.PAID, start=START, end=END):
        return await self.service.submit(
            self.session,
            self.employee.user_id,
            leave_type,
            start,
            end,
            None,
            None,
            "Family visit",
        )

    async def _approvals(self):
        return list(
            (
                await self.session.execute(
                    select(ApprovalRequestEntity).where(
                        ApprovalRequestEntity.action == "leave_approval"
                    )
                )
            )
            .scalars()
            .all()
        )

    async def _events(self, leave_request_id):
        return (
            await self.session.execute(
                select(
                    EventEntity.event_id, EventEntity.event_type, EventEntity.details
                )
                .where(
                    EventEntity.subject_type == "leave_request",
                    EventEntity.subject_id == leave_request_id,
                )
                .order_by(EventEntity.event_id)
            )
        ).all()

    async def _told(self, event_id) -> set[int]:
        rows = await self.session.execute(
            select(NotificationEntity.user_id).where(
                NotificationEntity.event_id == event_id
            )
        )
        return set(rows.scalars().all())

    async def _ledger(self):
        return list(
            (
                await self.session.execute(
                    select(LeaveLedgerEntity).where(
                        LeaveLedgerEntity.user_id == self.employee.user_id
                    )
                )
            )
            .scalars()
            .all()
        )

    async def test_filing_then_approving_writes_the_deduction(self):
        filed = await self._file()
        self.assertEqual(filed.status, "pending")
        self.assertEqual(filed.approver_user_id, self.manager.user_id)
        (approval,) = await self._approvals()
        self.assertEqual(approval.target_id, str(filed.request_id))
        self.assertEqual(approval.raised_by, self.employee.user_id)
        self.assertEqual(approval.reviewer_id, self.manager.user_id)

        decided = await self.service.decide(
            self.session, filed.request_id, self.manager.user_id, approve=True
        )

        self.assertEqual(decided.status, "approved")
        self.assertEqual(decided.decided_by, self.manager.user_id)
        self.assertIsNotNone(decided.decided_at)
        (entry,) = await self._ledger()
        self.assertEqual(entry.hours, -Decimal("24.00"))
        self.assertEqual(entry.created_by, self.manager.user_id)
        self.assertEqual(entry.source_request_id, filed.request_id)
        events = await self._events(filed.request_id)
        self.assertEqual(
            [e[1] for e in events], ["leave.request_submitted", "leave.request_decided"]
        )
        self.assertEqual(events[0][2]["startDate"], "2026-11-03")
        self.assertEqual(events[1][2]["decision"], "approved")
        self.assertEqual(await self._told(events[0][0]), {self.manager.user_id})
        self.assertEqual(await self._told(events[1][0]), {self.employee.user_id})

    async def test_a_rejection_needs_a_reason_and_writes_nothing(self):
        filed = await self._file()

        with self.assertRaises(ValueError):
            await self.service.decide(
                self.session, filed.request_id, self.manager.user_id, approve=False
            )
        decided = await self.service.decide(
            self.session,
            filed.request_id,
            self.manager.user_id,
            approve=False,
            comment="Release week",
        )

        self.assertEqual(decided.status, "rejected")
        self.assertEqual(decided.decision_comment, "Release week")
        self.assertEqual(await self._ledger(), [])
        own = await self.service.list_own(self.session, self.employee.user_id)
        self.assertEqual(own[0].decision_comment, "Release week")

    async def test_the_employee_withdraws_and_the_manager_is_told(self):
        filed = await self._file()

        withdrawn = await self.service.withdraw(
            self.session, filed.request_id, self.employee.user_id
        )

        self.assertEqual(withdrawn.status, "withdrawn")
        (approval,) = await self._approvals()
        self.assertIs(approval.status, ApprovalRequestStatus.WITHDRAWN)
        events = await self._events(filed.request_id)
        self.assertEqual(events[-1][2]["decision"], "withdrawn")
        self.assertEqual(await self._told(events[-1][0]), {self.manager.user_id})

    async def test_only_the_manager_decides_and_only_once(self):
        filed = await self._file()

        with self.assertRaises(PermissionError):
            await self.service.decide(
                self.session, filed.request_id, self.employee.user_id, approve=True
            )
        await self.service.decide(
            self.session, filed.request_id, self.manager.user_id, approve=True
        )
        with self.assertRaises(ConflictError):
            await self.service.decide(
                self.session, filed.request_id, self.manager.user_id, approve=True
            )
        self.assertEqual(len(await self._ledger()), 1)

    async def test_an_outsider_cannot_learn_a_requests_status(self):
        filed = await self._file()
        await self.service.decide(
            self.session, filed.request_id, self.manager.user_id, approve=True
        )
        outsider = _user("Out")
        await self.insert_entities([outsider])

        # Refused for who they are, not told the request is already decided.
        with self.assertRaises(PermissionError):
            await self.service.decide(
                self.session, filed.request_id, outsider.user_id, approve=True
            )
        with self.assertRaises(PermissionError):
            await self.service.withdraw(
                self.session, filed.request_id, outsider.user_id
            )

    async def test_a_holiday_entered_since_filing_blocks_the_approval(self):
        filed = await self._file()
        await self.insert_entities([
            LeaveHolidayEntity(
                year=2026, date=START, name="Late holiday", is_exchangeable=False
            )
        ])

        with self.assertRaises(ConflictError):
            await self.service.decide(
                self.session, filed.request_id, self.manager.user_id, approve=True
            )

        approvals = await self.service.list_for_approver(
            self.session, self.manager.user_id
        )
        self.assertEqual(approvals[0].status, "pending")
        self.assertEqual(await self._ledger(), [])

    async def test_short_sick_leave_is_approved_with_no_approval(self):
        filed = await self._file(LeaveRequestType.SICK, START, START)

        self.assertEqual(filed.status, "approved")
        self.assertIsNone(filed.decided_by)
        self.assertIsNotNone(filed.decided_at)
        self.assertEqual(await self._approvals(), [])
        # The manager still sees it with their team's requests.
        approvals = await self.service.list_for_approver(
            self.session, self.manager.user_id
        )
        self.assertEqual([a.request_id for a in approvals], [filed.request_id])
        with self.assertRaises(ConflictError):
            await self.service.withdraw(
                self.session, filed.request_id, self.employee.user_id
            )

    async def test_the_manager_sees_the_overdraft_as_it_stands_now(self):
        filed = await self._file()
        # Nothing has been granted, so 24 paid hours overdraw the balance.
        self.assertTrue(filed.is_overdraft)
        await self.insert_entities([
            LeaveLedgerEntity(
                user_id=self.employee.user_id,
                entry_type=LeaveEntryType.MANUAL_ADJUSTMENT,
                hours=Decimal("40.00"),
                effective_date=TODAY,
                created_by=self.manager.user_id,
                note="Granted after filing",
            )
        ])

        (row,) = await self.service.list_for_approver(
            self.session, self.manager.user_id
        )

        self.assertFalse(row.is_overdraft)


if __name__ == "__main__":
    unittest.main()
