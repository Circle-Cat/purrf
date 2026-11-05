"""The emails the leave request events turn into."""

import datetime
import unittest
from decimal import Decimal
from unittest.mock import AsyncMock, Mock, patch

from backend.common.leave_enums import (
    LEAVE_REQUEST_SUBJECT,
    LeaveEvent,
    LeaveRequestStatus,
    LeaveRequestType,
)
from backend.entity.approval_request_entity import ApprovalRequestEntity
from backend.entity.event_entity import EventEntity
from backend.entity.leave_request_entity import LeaveRequestEntity
from backend.entity.users_entity import UsersEntity
from backend.leave import notification_email_copy as copy
from backend.leave import notification_renderers  # noqa: F401 (registers)
from backend.leave import recipient_resolvers  # noqa: F401 (registers)
from backend.notification_management import recipient_registry, render_registry
from backend.repository.approval_request_repository import (
    ApprovalRequestRepository,
)
from backend.repository.leave_request_repository import LeaveRequestRepository
from backend.repository.users_repository import UsersRepository

EMPLOYEE = 10
MANAGER = 20
APPROVAL_ID = 301
LEAVE_ID = 501

SNAPSHOT = {
    "employeeName": "Ann Employee",
    "leaveType": "paid",
    "startDate": "2026-08-13",
    "endDate": "2026-08-15",
    "hours": "24.00",
}


def _user(user_id, first_name, last_name):
    row = UsersEntity(first_name=first_name, last_name=last_name)
    row.user_id = user_id
    row.preferred_name = None
    return row


def _leave(reason):
    return LeaveRequestEntity(
        leave_request_id=LEAVE_ID,
        user_id=EMPLOYEE,
        type=LeaveRequestType.PAID,
        start_date=datetime.date(2026, 8, 13),
        end_date=datetime.date(2026, 8, 15),
        hours=Decimal("24.00"),
        status=LeaveRequestStatus.PENDING,
        approver_user_id=MANAGER,
        reason=reason,
    )


def _approval(comment):
    row = ApprovalRequestEntity(
        raised_by=EMPLOYEE, reviewer_id=MANAGER, decision_comment=comment
    )
    row.request_id = APPROVAL_ID
    return row


def _event(event_type, actor_id, **details):
    return EventEntity(
        subject_type=LEAVE_REQUEST_SUBJECT,
        subject_id=LEAVE_ID,
        actor_id=actor_id,
        event_type=event_type,
        details={**SNAPSHOT, "requestId": APPROVAL_ID, **details},
    )


class LeaveRenderTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.session = Mock()
        self.people = {
            EMPLOYEE: _user(EMPLOYEE, "Ann", "Employee"),
            MANAGER: _user(MANAGER, "Bob", "Manager"),
        }
        self.leave = _leave("Family wedding")
        self.approval = _approval("Enjoy it.")
        for cls, name, side_effect in (
            (
                UsersRepository,
                "get_user_by_user_id",
                lambda _s, user_id: self.people.get(user_id),
            ),
            (
                LeaveRequestRepository,
                "get_by_id",
                lambda _s, leave_id: self.leave if leave_id == LEAVE_ID else None,
            ),
            (
                ApprovalRequestRepository,
                "get",
                lambda _s, request_id: (
                    self.approval if request_id == APPROVAL_ID else None
                ),
            ),
        ):
            patcher = patch.object(
                cls, name, new_callable=AsyncMock, side_effect=side_effect
            )
            patcher.start()
            self.addCleanup(patcher.stop)

    async def _render(self, event):
        return await render_registry.render(self.session, event)

    async def _submitted(self):
        return await self._render(_event(LeaveEvent.REQUEST_SUBMITTED, EMPLOYEE))

    async def _decided(self, decision="approved", actor_id=MANAGER):
        return await self._render(
            _event(LeaveEvent.REQUEST_DECIDED, actor_id, decision=decision)
        )

    # -- filed -------------------------------------------------------------

    async def test_a_filed_request_tells_the_manager_what_was_asked(self):
        subject, body = await self._submitted()

        self.assertEqual(subject, "A leave request is waiting for your decision")
        self.assertIn(
            "Ann Employee asked for paid leave from 2026-08-13 to 2026-08-15 "
            "(24.00 hours).",
            body,
        )
        self.assertIn("<p>Their reason: Family wedding</p>", body)
        self.assertIn("Approvals", body)

    async def test_what_was_asked_comes_from_the_snapshot_not_the_row(self):
        """An email delivered late says what was true when it was filed."""
        self.leave.hours = Decimal("8.00")
        self.leave.start_date = datetime.date(2026, 9, 1)

        _, body = await self._submitted()

        self.assertIn("2026-08-13", body)
        self.assertIn("24.00 hours", body)
        self.assertNotIn("2026-09-01", body)

    async def test_no_reason_line_when_the_employee_gave_none(self):
        for reason in (None, "", "   "):
            with self.subTest(reason=reason):
                self.leave = _leave(reason)

                _, body = await self._submitted()

                self.assertNotIn("Their reason", body)

    async def test_no_reason_line_when_the_request_is_gone(self):
        self.leave = None

        _, body = await self._submitted()

        self.assertNotIn("Their reason", body)
        self.assertIn("Ann Employee", body)

    async def test_the_name_and_the_reason_are_escaped(self):
        self.leave = _leave("<script>alert(1)</script>")
        event = _event(
            LeaveEvent.REQUEST_SUBMITTED, EMPLOYEE, employeeName="<b>Ann</b> & Co"
        )

        subject, body = await self._render(event)

        self.assertNotIn("<script>", body)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", body)
        self.assertIn("&lt;b&gt;Ann&lt;/b&gt; &amp; Co", body)
        self.assertNotIn("Ann", subject)

    async def test_a_missing_name_still_reads_as_a_sentence(self):
        event = _event(LeaveEvent.REQUEST_SUBMITTED, EMPLOYEE, employeeName="")

        _, body = await self._render(event)

        self.assertIn("Somebody asked for paid leave", body)

    async def test_one_day_reads_as_on_that_day(self):
        event = _event(
            LeaveEvent.REQUEST_SUBMITTED,
            EMPLOYEE,
            leaveType="sick",
            endDate="2026-08-13",
            hours="4.00",
        )

        _, body = await self._render(event)

        self.assertIn("asked for sick leave on 2026-08-13 (4.00 hours).", body)

    async def test_an_exchange_and_an_unknown_type_read_naturally(self):
        for leave_type, words in (
            ("exchange", "asked for a holiday exchange"),
            ("mystery", "asked for leave"),
        ):
            with self.subTest(leave_type=leave_type):
                _, body = await self._render(
                    _event(LeaveEvent.REQUEST_SUBMITTED, EMPLOYEE, leaveType=leave_type)
                )

                self.assertIn(words, body)

    # -- decided -----------------------------------------------------------

    async def test_an_approval_names_the_manager_and_their_comment(self):
        subject, body = await self._decided("approved")

        self.assertEqual(subject, "Your leave request was approved")
        self.assertIn(
            "Bob Manager approved your request for paid leave from 2026-08-13 "
            "to 2026-08-15.",
            body,
        )
        self.assertIn("<p>Their reason: Enjoy it.</p>", body)

    async def test_a_rejection_says_so_and_why(self):
        self.approval = _approval("No cover that week.")

        subject, body = await self._decided("rejected")

        self.assertEqual(subject, "Your leave request was rejected")
        self.assertIn("Bob Manager rejected your request", body)
        self.assertIn("<p>Their reason: No cover that week.</p>", body)

    async def test_no_reason_line_on_an_approval_without_a_comment(self):
        self.approval = _approval(None)

        _, body = await self._decided("approved")

        self.assertNotIn("Their reason", body)

    async def test_the_comment_and_the_manager_name_are_escaped(self):
        self.approval = _approval('<img src=x onerror="steal()">')
        self.people[MANAGER] = _user(MANAGER, "<i>Bob</i>", "Manager")

        subject, body = await self._decided("rejected")

        self.assertNotIn("<img", body)
        self.assertNotIn("<i>", body)
        self.assertIn("&lt;img src=x onerror=&quot;steal()&quot;&gt;", body)
        self.assertIn("&lt;i&gt;Bob&lt;/i&gt; Manager", body)
        self.assertEqual(subject, "Your leave request was rejected")

    async def test_a_manager_who_cannot_be_named_is_your_manager(self):
        for actor_id in (None, 404):
            with self.subTest(actor_id=actor_id):
                _, body = await self._decided("approved", actor_id=actor_id)

                self.assertIn("Your manager approved your request", body)

    # -- withdrawn ---------------------------------------------------------

    async def test_a_withdrawal_tells_the_manager_there_is_nothing_to_do(self):
        subject, body = await self._decided("withdrawn", actor_id=EMPLOYEE)

        self.assertEqual(subject, "A leave request was withdrawn")
        self.assertIn(
            "Ann Employee withdrew their request for paid leave from 2026-08-13 "
            "to 2026-08-15.",
            body,
        )
        self.assertIn("nothing left for you to do", body)
        self.assertNotIn("approved", body)
        self.assertNotIn("rejected", body)
        self.assertNotIn("Their reason", body)

    async def test_a_withdrawal_escapes_the_name(self):
        _, body = await self._render(
            _event(
                LeaveEvent.REQUEST_DECIDED,
                EMPLOYEE,
                decision="withdrawn",
                employeeName="<script>x</script>",
            )
        )

        self.assertNotIn("<script>", body)
        self.assertIn("&lt;script&gt;x&lt;/script&gt;", body)

    # -- wiring ------------------------------------------------------------

    def test_every_event_that_notifies_also_renders(self):
        for event_type in (LeaveEvent.REQUEST_SUBMITTED, LeaveEvent.REQUEST_DECIDED):
            with self.subTest(event_type=event_type):
                self.assertIn(event_type, recipient_registry._RESOLVERS)
                self.assertIn(event_type, render_registry._RENDERERS)


class LeaveEmailCopyTest(unittest.TestCase):
    """The copy on its own: names arrive escaped, person-written text does
    not, and nothing person-written reaches a subject."""

    def test_the_reason_is_escaped_here_but_the_name_is_trusted(self):
        _, body = copy.request_submitted(
            "Ann &amp; Co", "paid", "2026-08-13", "2026-08-13", "8.00", "<b>me</b>"
        )

        self.assertIn("Ann &amp; Co asked", body)
        self.assertNotIn("&amp;amp;", body)
        self.assertIn("&lt;b&gt;me&lt;/b&gt;", body)

    def test_hours_are_left_out_when_unknown(self):
        _, body = copy.request_submitted(
            "Ann", "paid", "2026-08-13", "2026-08-14", None, None
        )

        self.assertIn("from 2026-08-13 to 2026-08-14.</p>", body)
        self.assertNotIn("hours", body)

    def test_anything_but_approved_reads_as_rejected(self):
        subject, body = copy.request_decided(
            "Bob", "", "paid", "2026-08-13", None, "  Busy.  "
        )

        self.assertEqual(subject, "Your leave request was rejected")
        self.assertIn("Bob rejected your request for paid leave on 2026-08-13.", body)
        self.assertIn("<p>Their reason: Busy.</p>", body)

    def test_every_email_carries_the_footer(self):
        for _, body in (
            copy.request_submitted("A", "paid", "2026-08-13", None, "8.00", None),
            copy.request_decided("B", "approved", "paid", "2026-08-13", None, None),
            copy.request_withdrawn("A", "paid", "2026-08-13", None),
        ):
            self.assertIn("This is an automated message from Purrf.", body)


if __name__ == "__main__":
    unittest.main()
