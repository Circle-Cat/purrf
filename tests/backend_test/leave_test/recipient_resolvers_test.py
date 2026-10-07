"""Who hears about each leave request event."""

import unittest
from unittest.mock import AsyncMock, Mock, patch

from backend.common.leave_enums import LEAVE_REQUEST_SUBJECT, LeaveEvent
from backend.entity.approval_request_entity import ApprovalRequestEntity
from backend.entity.event_entity import EventEntity
from backend.leave import recipient_resolvers  # noqa: F401 (registers)
from backend.notification_management import recipient_registry
from backend.repository.approval_request_repository import (
    ApprovalRequestRepository,
)

EMPLOYEE = 10
MANAGER = 20
# Distinct from the leave request id the event is about, so reading one where
# the other belongs finds nothing.
APPROVAL_ID = 301
LEAVE_ID = 501


def _approval():
    row = ApprovalRequestEntity(raised_by=EMPLOYEE, reviewer_id=MANAGER)
    row.request_id = APPROVAL_ID
    return row


def _event(event_type, **details):
    return EventEntity(
        subject_type=LEAVE_REQUEST_SUBJECT,
        subject_id=LEAVE_ID,
        actor_id=None,
        event_type=event_type,
        details={"requestId": APPROVAL_ID, **details},
    )


class LeaveRecipientsTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.session = Mock()
        self.approvals = {APPROVAL_ID: _approval()}
        lookup = patch.object(
            ApprovalRequestRepository,
            "get",
            new_callable=AsyncMock,
            side_effect=lambda _session, request_id: self.approvals.get(request_id),
        )
        self.get = lookup.start()
        self.addCleanup(lookup.stop)

    async def _resolve(self, event):
        return await recipient_registry.resolve_recipients(self.session, event)

    async def test_a_filed_request_goes_to_the_manager_it_waits_on(self):
        recipients = await self._resolve(_event(LeaveEvent.REQUEST_SUBMITTED))

        self.assertEqual(recipients, {MANAGER})
        self.get.assert_awaited_once_with(self.session, APPROVAL_ID)

    async def test_a_decision_goes_to_the_employee(self):
        for decision in ("approved", "rejected"):
            with self.subTest(decision=decision):
                recipients = await self._resolve(
                    _event(LeaveEvent.REQUEST_DECIDED, decision=decision)
                )

                self.assertEqual(recipients, {EMPLOYEE})

    async def test_a_withdrawal_goes_back_to_the_manager(self):
        recipients = await self._resolve(
            _event(LeaveEvent.REQUEST_DECIDED, decision="withdrawn")
        )

        self.assertEqual(recipients, {MANAGER})

    async def test_an_event_naming_no_request_fails_loudly(self):
        """Telling nobody about a request is the silent failure this avoids."""
        event = _event(LeaveEvent.REQUEST_SUBMITTED)
        del event.details["requestId"]

        with self.assertRaises(ValueError):
            await self._resolve(event)

    async def test_an_event_naming_an_unknown_request_fails_loudly(self):
        self.approvals.clear()

        with self.assertRaises(ValueError):
            await self._resolve(_event(LeaveEvent.REQUEST_DECIDED, decision="approved"))

    async def test_an_event_about_something_else_is_refused(self):
        """subject_id would otherwise be read as an id of the wrong table."""
        event = _event(LeaveEvent.REQUEST_SUBMITTED)
        event.subject_type = "application"

        with self.assertRaises(ValueError):
            await self._resolve(event)

    async def test_reassignment_notifies_nobody(self):
        """A leave request's approver is never reassigned, so the event has no
        resolver at all."""
        recipients = await self._resolve(_event(LeaveEvent.REQUEST_REASSIGNED))

        self.assertEqual(recipients, set())
        self.get.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
