"""Submitting, withdrawing and deciding a leave request.

Almost every case here is a refusal, and each refusal exists because the thing
it prevents is silent: hours deducted twice, a ledger row written behind a
frozen year, somebody's request approved by nobody.
"""

import datetime
import json
from decimal import Decimal
from unittest import IsolatedAsyncioTestCase, main
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy.exc import IntegrityError

from backend.approval.approval_service import APPROVAL_CHECKS_FAILED, ApprovalService
from backend.common.approval_enums import ApprovalRequestStatus
from backend.common.exceptions import ConflictError
from backend.common.leave_enums import (
    LEAVE_APPROVAL,
    LEAVE_REQUEST_SUBJECT,
    LeaveEntryType,
    LeaveEvent,
    LeaveRequestStatus,
    LeaveRequestType,
)
from backend.dto.leave_request_dto import LeaveRequestDto
from backend.entity.approval_request_entity import ApprovalRequestEntity
from backend.entity.leave_holiday_entity import LeaveHolidayEntity
from backend.entity.leave_request_entity import LeaveRequestEntity
from backend.entity.users_entity import UsersEntity
from backend.leave.leave_participants import ResolvedParticipants
from backend.leave.leave_request_handler import LeaveRequestHandler
from backend.leave.leave_request_service import LeaveRequestService

TODAY = datetime.date(2026, 8, 5)
# Thursday to Saturday, three working days (the weekend is Sunday and Monday).
LEAVE_START = datetime.date(2026, 8, 13)
LEAVE_END = datetime.date(2026, 8, 15)

EMPLOYEE = 10
MANAGER = 20
STRANGER = 99

# The id a flush hands back, so a filed request has one to be read by.
FILED_REQUEST_ID = 900
# A request already on file. Approval ids start at 301, so an approval id read
# where a leave id belongs (or the other way round) finds nothing.
STORED_REQUEST_ID = 501
FIRST_APPROVAL_ID = 301

FILED_AT = datetime.datetime(2026, 8, 5, 9, 30, tzinfo=datetime.timezone.utc)


def _holiday(day, is_exchangeable=False, name="Company holiday"):
    return LeaveHolidayEntity(
        year=day.year, date=day, name=name, is_exchangeable=is_exchangeable
    )


def _stored_request(
    request_type=LeaveRequestType.PAID,
    hours="24.00",
    status=LeaveRequestStatus.PENDING,
    request_id=STORED_REQUEST_ID,
    start_date=LEAVE_START,
    end_date=LEAVE_END,
    is_overdraft=False,
):
    """A request as the database holds it."""
    return LeaveRequestEntity(
        leave_request_id=request_id,
        user_id=EMPLOYEE,
        type=request_type,
        start_date=start_date,
        end_date=end_date,
        start_time=None,
        end_time=None,
        hours=Decimal(hours),
        status=status,
        approver_user_id=MANAGER,
        reason="Holiday",
        is_overdraft=is_overdraft,
        is_late_notice=False,
        created_timestamp=FILED_AT,
    )


def _user(user_id, first_name, last_name, is_active=True):
    row = UsersEntity(first_name=first_name, last_name=last_name)
    row.user_id = user_id
    row.preferred_name = None
    row.is_active = is_active
    row.is_blocked = False
    return row


def _email(address):
    row = MagicMock()
    row.email = address
    return row


class _FakeLeaveRequests:
    """The leave request rows the service and the handler share.

    One store for both, so a status the handler writes is the status the
    service reads back -- a MagicMock per caller would let either side pass
    against a row the other never saw.
    """

    def __init__(self):
        self.rows: dict[int, LeaveRequestEntity] = {}
        self.add = AsyncMock(side_effect=self._add)
        self.get_by_id = AsyncMock(side_effect=self._get_by_id)
        self.list_overlapping = AsyncMock(return_value=[])
        self.sum_pending_paid_hours = AsyncMock(return_value=Decimal("0.00"))
        self.list_for_user = AsyncMock(return_value=[])
        self.list_for_approver = AsyncMock(return_value=[])

    def put(self, request):
        self.rows[request.leave_request_id] = request
        return request

    async def _add(self, session, request):
        # add() flushes in production, so the row comes back with an id.
        request.leave_request_id = FILED_REQUEST_ID
        request.created_timestamp = FILED_AT
        return self.put(request)

    async def _get_by_id(self, session, request_id, *, for_update=False):
        return self.rows.get(request_id)


class _FakeApprovalRequests:
    """In-memory ApprovalRequestRepository with the real one's semantics:
    closing only touches a pending row, and a second pending request on one
    target is refused the way the partial unique index refuses it."""

    def __init__(self):
        self.rows: list[ApprovalRequestEntity] = []
        self._next_id = FIRST_APPROVAL_ID

    def add(self, **fields) -> ApprovalRequestEntity:
        row = ApprovalRequestEntity(**fields)
        row.request_id = self._next_id
        row.created_at = datetime.datetime.now(datetime.timezone.utc)
        self._next_id += 1
        self.rows.append(row)
        return row

    async def create(
        self,
        session,
        *,
        action,
        target_type,
        target_id,
        payload,
        reason,
        raised_by,
        reviewer_id,
    ):
        if await self.get_pending_for_target(session, action, target_type, target_id):
            raise IntegrityError("INSERT", {}, Exception("pending target"))
        return self.add(
            action=action,
            target_type=target_type,
            target_id=target_id,
            payload=payload,
            reason=reason,
            raised_by=raised_by,
            reviewer_id=reviewer_id,
            status=ApprovalRequestStatus.PENDING,
        )

    async def get(self, session, request_id, *, for_update=False):
        return next((r for r in self.rows if r.request_id == request_id), None)

    async def get_pending_for_target(self, session, action, target_type, target_id):
        return next(
            (
                r
                for r in self.rows
                if r.action == action
                and r.target_type == target_type
                and r.target_id == target_id
                and r.status == ApprovalRequestStatus.PENDING
            ),
            None,
        )

    async def list_latest_for_targets(self, session, action, target_type, target_ids):
        latest = {}
        for row in self.rows:
            if (
                row.action == action
                and row.target_type == target_type
                and row.target_id in target_ids
            ):
                latest[row.target_id] = row
        return list(latest.values())

    async def close(self, session, request_id, *, status, decided_by, decision_comment):
        row = await self.get(session, request_id)
        if row is None or row.status != ApprovalRequestStatus.PENDING:
            return False
        row.status = status
        row.decided_by = decided_by
        row.decided_at = datetime.datetime.now(datetime.timezone.utc)
        row.decision_comment = decision_comment
        return True


class LeaveRequestServiceTest(IsolatedAsyncioTestCase):
    def setUp(self):
        self.logger = MagicMock()
        self.requests = _FakeLeaveRequests()
        self.ledger = MagicMock()
        self.ledger.add_entries = AsyncMock()
        self.ledger.balance = AsyncMock(return_value=Decimal("80.00"))
        self.holidays = MagicMock()
        self.holidays.list_by_year = AsyncMock(
            return_value=[
                _holiday(datetime.date(2026, 6, 19), name="Dragon Boat Festival")
            ]
        )
        self.emails = MagicMock()
        self.emails.list_by_user_id = AsyncMock(
            return_value=[_email("ann@circlecat.org")]
        )
        self.emails.get_emails_by_user_ids = AsyncMock(return_value={})
        self.ledger.balances_by_user_ids = AsyncMock(return_value={})
        self.ledger.sum_deductions_for_year = AsyncMock(return_value=Decimal("0.00"))
        self.people = {
            EMPLOYEE: _user(EMPLOYEE, "Ann", "Employee"),
            MANAGER: _user(MANAGER, "Bob", "Manager"),
        }
        self.users = MagicMock()
        self.users.get_all_by_ids = AsyncMock(return_value=[])
        self.users.get_user_by_user_id = AsyncMock(
            side_effect=lambda _session, user_id: self.people.get(user_id)
        )
        self.redis_client = MagicMock()
        self.redis_client.hgetall.return_value = {
            "ann": json.dumps({
                "level": "L3",
                "annual_hours": 80,
                "hire_date": "2024-03-01",
                "leave_date": None,
                "manager_ldap": "bob",
                "account_enabled": True,
                "problems": [],
            })
        }
        self.retry_utils = MagicMock()
        self.retry_utils.get_retry_on_transient = lambda fn, *a, **kw: fn(*a, **kw)
        self.resolver = MagicMock()
        self.resolver.resolve = AsyncMock(
            return_value=ResolvedParticipants(
                by_ldap={"bob": MANAGER}, unresolved=(), not_internal=()
            )
        )
        self.session = MagicMock()
        self.session.commit = AsyncMock()

        self.record_event = AsyncMock()
        recorder = patch(
            "backend.approval.approval_service.record_event", new=self.record_event
        )
        recorder.start()
        self.addCleanup(recorder.stop)

        self.approval_requests = _FakeApprovalRequests()
        self.approval_service = ApprovalService(
            approval_request_repository=self.approval_requests,
            user_permissions_repository=MagicMock(),
            users_repository=self.users,
            logger=MagicMock(),
            handlers=[
                LeaveRequestHandler(
                    leave_request_repository=self.requests,
                    leave_ledger_repository=self.ledger,
                    leave_holiday_repository=self.holidays,
                    users_repository=self.users,
                )
            ],
        )
        self.service = LeaveRequestService(
            logger=self.logger,
            leave_request_repository=self.requests,
            leave_ledger_repository=self.ledger,
            leave_holiday_repository=self.holidays,
            user_emails_repository=self.emails,
            users_repository=self.users,
            redis_client=self.redis_client,
            retry_utils=self.retry_utils,
            participant_resolver=self.resolver,
            approval_service=self.approval_service,
        )
        self._set_today(TODAY)

    def _set_today(self, day):
        """The service judges a filing and the handler an approval against
        the same business day."""
        for module in (
            "backend.leave.leave_request_service",
            "backend.leave.leave_request_handler",
        ):
            clock = patch(f"{module}.business_today", return_value=day)
            clock.start()
            self.addCleanup(clock.stop)

    async def _submit(self, **overrides):
        payload = {
            "user_id": EMPLOYEE,
            "request_type": LeaveRequestType.PAID,
            "start_date": LEAVE_START,
            "end_date": LEAVE_END,
            "start_time": None,
            "end_time": None,
            "reason": "Holiday",
        }
        payload.update(overrides)
        return await self.service.submit(self.session, **payload)

    def _stored(self):
        return self.requests.add.await_args.args[1]

    def _pending(self, **fields):
        """A request on file and waiting on its manager, as submit leaves it."""
        request = self.requests.put(_stored_request(**fields))
        self.approval_requests.add(
            action=LEAVE_APPROVAL,
            target_type=LEAVE_REQUEST_SUBJECT,
            target_id=str(request.leave_request_id),
            payload={},
            reason=None,
            raised_by=EMPLOYEE,
            reviewer_id=MANAGER,
            status=ApprovalRequestStatus.PENDING,
        )
        return request

    def _approval_for(self, request_id):
        return next(
            row
            for row in self.approval_requests.rows
            if row.target_id == str(request_id)
        )

    def _ledger_rows(self):
        return [
            entry
            for call in self.ledger.add_entries.await_args_list
            for entry in call.args[1]
        ]


class TestTheShapeADecisionAnswersWith(LeaveRequestServiceTest):
    """Filing, taking back and deciding answer with the read model.

    They used to answer with the stored row. FastAPI's encoder falls through to
    ``vars()`` for an ORM object, so the same resource came back in snake_case
    from these three and camelCase from the two lists, and ``hours`` went
    through the Decimal encoder into a float -- which is the one thing
    LeaveRequestDto exists to prevent.
    """

    async def test_filing_answers_with_a_read_model(self):
        filed = await self._submit()

        self.assertIsInstance(filed, LeaveRequestDto)
        self.assertEqual(filed.request_id, FILED_REQUEST_ID)

    async def test_hours_come_back_as_text_fixed_to_two_decimals(self):
        """A float would show 78.46 as 78.45999999999999. A balance is a
        money-shaped figure and must not be touched by floating point."""
        filed = await self._submit()

        self.assertEqual(filed.hours, "24.00")

    async def test_the_keys_are_the_ones_the_lists_send(self):
        """One resource, one shape. The employee's own list and the response to
        filing it describe the same request."""
        filed = await self._submit()

        self.assertIn("requestId", filed.model_dump(by_alias=True))
        self.assertNotIn("leave_request_id", filed.model_dump(by_alias=True))

    async def test_the_notice_the_rule_asked_for_comes_back_too(self):
        """Three days of paid leave owe six working days of notice. Sending it
        from the lists but not from here would make one request read as two."""
        filed = await self._submit()

        self.assertEqual(filed.required_notice_workdays, 6)

    async def test_deciding_answers_with_a_read_model(self):
        self._pending()

        decided = await self.service.decide(
            self.session, STORED_REQUEST_ID, MANAGER, approve=True
        )

        self.assertIsInstance(decided, LeaveRequestDto)
        self.assertEqual(decided.request_id, STORED_REQUEST_ID)
        self.assertEqual(decided.status, LeaveRequestStatus.APPROVED.value)
        self.assertEqual(decided.hours, "24.00")

    async def test_withdrawing_answers_with_a_read_model(self):
        self._pending()

        withdrawn = await self.service.withdraw(
            self.session, STORED_REQUEST_ID, EMPLOYEE
        )

        self.assertIsInstance(withdrawn, LeaveRequestDto)
        self.assertEqual(withdrawn.request_id, STORED_REQUEST_ID)
        self.assertEqual(withdrawn.status, LeaveRequestStatus.WITHDRAWN.value)


class TestSubmit(LeaveRequestServiceTest):
    async def test_a_request_is_stored_pending_with_its_hours(self):
        request = await self._submit()

        self.assertEqual(request.status, LeaveRequestStatus.PENDING)
        self.assertEqual(request.hours, "24.00")
        self.assertEqual(request.user_id, EMPLOYEE)
        self.session.commit.assert_awaited_once()

    async def test_the_approver_is_the_manager_azure_names_today(self):
        """A snapshot, not a lookup at decision time: changing manager later
        must not repoint a request somebody has already decided."""
        request = await self._submit()

        self.assertEqual(request.approver_user_id, MANAGER)

    async def test_filing_raises_an_approval_naming_the_manager(self):
        """The manager snapshotted on the row is who the approval waits on;
        nobody chooses or changes it."""
        await self._submit()

        [approval] = self.approval_requests.rows
        self.assertEqual(approval.action, LEAVE_APPROVAL)
        self.assertEqual(approval.target_type, LEAVE_REQUEST_SUBJECT)
        self.assertEqual(approval.target_id, str(FILED_REQUEST_ID))
        self.assertEqual(approval.raised_by, EMPLOYEE)
        self.assertEqual(approval.reviewer_id, MANAGER)
        self.assertEqual(approval.status, ApprovalRequestStatus.PENDING)
        self.assertIsNone(approval.reason)

    async def test_filing_tells_the_manager_what_was_asked_for(self):
        """The event carries a snapshot of the request, so a notification
        delivered late still says what was true when it was filed."""
        await self._submit()

        self.record_event.assert_awaited_once()
        kwargs = self.record_event.await_args.kwargs
        self.assertEqual(kwargs["event_type"], LeaveEvent.REQUEST_SUBMITTED)
        self.assertEqual(kwargs["subject_type"], LEAVE_REQUEST_SUBJECT)
        self.assertEqual(kwargs["subject_id"], FILED_REQUEST_ID)
        self.assertEqual(kwargs["actor_id"], EMPLOYEE)
        self.assertEqual(
            kwargs["details"],
            {
                "employeeName": "Ann Employee",
                "leaveType": "paid",
                "startDate": "2026-08-13",
                "endDate": "2026-08-15",
                "hours": "24.00",
                "requestId": FIRST_APPROVAL_ID,
                "action": LEAVE_APPROVAL,
            },
        )

    async def test_a_filed_request_has_not_been_decided(self):
        filed = await self._submit()

        self.assertIsNone(filed.decided_by)
        self.assertIsNone(filed.decided_at)
        self.assertIsNone(filed.decision_comment)

    async def test_a_manager_who_can_no_longer_approve_refuses_the_filing(self):
        """A deactivated manager would leave the request waiting on somebody
        who can never sign in to decide it."""
        self.people[MANAGER].is_active = False

        with self.assertRaises(ValueError):
            await self._submit()

        self.assertEqual(self.approval_requests.rows, [])
        self.session.commit.assert_not_awaited()

    async def test_nothing_reaches_the_ledger_until_a_decision(self):
        """The ledger records facts. A request nobody has decided is not one,
        and a row written now could never be taken back."""
        await self._submit()

        self.ledger.add_entries.assert_not_awaited()

    async def test_leave_starting_in_the_past_is_refused(self):
        """Otherwise the ledger gets rewritten behind a year the annual close
        has already settled."""
        with self.assertRaises(ValueError):
            await self._submit(
                start_date=datetime.date(2026, 8, 4), end_date=datetime.date(2026, 8, 4)
            )

        self.requests.add.assert_not_awaited()

    async def test_leave_starting_today_is_allowed(self):
        """Late notice, not a refusal."""
        request = await self._submit(start_date=TODAY, end_date=TODAY)

        self.assertTrue(request.is_late_notice)

    async def test_a_year_with_no_company_holidays_is_refused(self):
        """Without the calendar the hours would be computed against a year
        that has no holidays in it, and quietly come out too high."""
        self.holidays.list_by_year.return_value = []

        with self.assertRaises(ValueError):
            await self._submit()

        self.requests.add.assert_not_awaited()

    async def test_a_clash_with_another_request_is_refused_by_name(self):
        """The message has to name what it clashed with; "overlaps" alone
        leaves somebody hunting through their own history."""
        clash = MagicMock()
        clash.leave_request_id = 501
        clash.start_date = LEAVE_START
        clash.end_date = LEAVE_END
        self.requests.list_overlapping.return_value = [clash]

        with self.assertRaises(ValueError) as caught:
            await self._submit()

        self.assertIn("501", str(caught.exception))
        self.requests.add.assert_not_awaited()

    async def test_a_request_worth_no_hours_is_refused(self):
        """A Sunday and a Monday: nothing to deduct, so there is nothing to
        ask for."""
        with self.assertRaises(ValueError):
            await self._submit(
                start_date=datetime.date(2026, 8, 9),
                end_date=datetime.date(2026, 8, 10),
            )

    async def test_somebody_azure_has_no_manager_for_cannot_submit(self):
        """Blocking beats auto-approving: a blank field in Azure would
        otherwise become leave nobody approved, and it could not be undone
        afterwards. The message has to say it is the Azure record."""
        self.redis_client.hgetall.return_value = {
            "ann": json.dumps({
                "level": "L3",
                "annual_hours": 80,
                "hire_date": "2024-03-01",
                "leave_date": None,
                "manager_ldap": None,
                "account_enabled": True,
                "problems": ["missing_manager"],
            })
        }

        with self.assertRaises(ValueError) as caught:
            await self._submit()

        self.assertIn("Azure", str(caught.exception))
        self.assertEqual(self.approval_requests.rows, [])
        self.requests.add.assert_not_awaited()

    async def test_a_manager_with_no_purrf_account_cannot_be_an_approver(self):
        self.resolver.resolve.return_value = ResolvedParticipants(
            by_ldap={}, unresolved=("bob",), not_internal=()
        )

        with self.assertRaises(ValueError):
            await self._submit()

        self.assertEqual(self.approval_requests.rows, [])
        self.requests.add.assert_not_awaited()

    async def test_somebody_outside_the_leave_system_cannot_submit(self):
        self.redis_client.hgetall.return_value = {}

        with self.assertRaises(ValueError):
            await self._submit()

        self.assertEqual(self.approval_requests.rows, [])
        self.requests.add.assert_not_awaited()

    async def test_somebody_with_no_corporate_address_cannot_submit(self):
        """Their Azure profile is found by ldap, and the corporate address is
        the only thing that ties a purrf account to one."""
        self.emails.list_by_user_id.return_value = [_email("ann@gmail.com")]

        with self.assertRaises(ValueError):
            await self._submit()

        self.assertEqual(self.approval_requests.rows, [])
        self.requests.add.assert_not_awaited()


class TestNoticeAndOverdraft(LeaveRequestServiceTest):
    async def test_enough_notice_leaves_the_flag_clear(self):
        """Three days off asked for on 5 August: six working days, exactly the
        six they need."""
        request = await self._submit()

        self.assertFalse(request.is_late_notice)

    async def test_a_day_less_notice_sets_the_flag_but_still_submits(self):
        """A soft mark. The manager decides; the system does not refuse."""
        self._set_today(datetime.date(2026, 8, 6))

        request = await self._submit()

        self.assertTrue(request.is_late_notice)
        self.assertEqual(request.status, LeaveRequestStatus.PENDING)

    async def test_sick_leave_is_never_late(self):
        """Nobody schedules illness, and a mark nobody can act on is noise."""
        self._set_today(datetime.date(2026, 8, 12))

        request = await self._submit(request_type=LeaveRequestType.SICK)

        self.assertFalse(request.is_late_notice)

    async def test_a_balance_that_cannot_cover_it_is_marked_not_refused(self):
        """An L1 has no entitlement at all, so refusing on the balance would
        leave them unable to take a single paid day."""
        self.ledger.balance.return_value = Decimal("8.00")

        request = await self._submit()

        self.assertTrue(request.is_overdraft)
        self.assertEqual(request.status, LeaveRequestStatus.PENDING)

    async def test_hours_already_waiting_on_a_decision_count_against_it(self):
        """Two pending requests must not both be paid out of the same hours."""
        self.ledger.balance.return_value = Decimal("32.00")
        self.requests.sum_pending_paid_hours.return_value = Decimal("16.00")

        request = await self._submit()

        self.assertTrue(request.is_overdraft)

    async def test_sick_leave_is_never_an_overdraft(self):
        """It does not touch the balance."""
        self.ledger.balance.return_value = Decimal("0.00")

        request = await self._submit(request_type=LeaveRequestType.SICK)

        self.assertFalse(request.is_overdraft)


class TestSickLeave(LeaveRequestServiceTest):
    async def test_three_days_or_less_is_approved_on_submission(self):
        """The rule is "over three days, talk to your manager", so three days
        exactly is approved. decided_by stays empty: nobody decided it, and it
        was decided when it was filed."""
        request = await self._submit(request_type=LeaveRequestType.SICK)

        self.assertEqual(request.status, LeaveRequestStatus.APPROVED)
        self.assertIsNone(request.decided_by)
        self.assertEqual(request.decided_at, FILED_AT)
        self.assertIsNone(request.decision_comment)

    async def test_approved_on_submission_raises_no_approval(self):
        """It never goes to the manager, so nobody is asked and nobody is
        told."""
        await self._submit(request_type=LeaveRequestType.SICK)

        self.assertEqual(self.approval_requests.rows, [])
        self.record_event.assert_not_awaited()
        self.session.commit.assert_awaited_once()

    async def test_a_fourth_day_puts_it_in_front_of_the_manager(self):
        """24h exactly is approved on submission; the next working day past it
        is not. 13 to 18 August spans four working days -- the 16th is a Sunday
        and the 17th a Monday, so they do not count towards the hours either."""
        four_days = await self._submit(
            request_type=LeaveRequestType.SICK,
            start_date=LEAVE_START,
            end_date=datetime.date(2026, 8, 18),
        )

        self.assertEqual(four_days.hours, "32.00")
        self.assertEqual(four_days.status, LeaveRequestStatus.PENDING)
        self.assertIsNone(four_days.decided_at)
        [approval] = self.approval_requests.rows
        self.assertEqual(approval.reviewer_id, MANAGER)

    async def test_an_approved_sick_request_writes_nothing_to_the_ledger(self):
        """Sick leave has no annual allowance and deducts nothing, so there is
        no row -- not even a zero one."""
        await self._submit(request_type=LeaveRequestType.SICK)

        self.ledger.add_entries.assert_not_awaited()

    async def test_an_approver_is_still_recorded(self):
        """The approval is automatic; the approver is not absent. Without one
        the request could not be submitted at all, sick or otherwise."""
        request = await self._submit(request_type=LeaveRequestType.SICK)

        self.assertEqual(request.approver_user_id, MANAGER)

    async def test_it_cannot_be_decided_afterwards(self):
        """No approval waits on it, so there is nothing to decide -- and a
        second look would write nothing anyway, since it was never pending."""
        await self._submit(request_type=LeaveRequestType.SICK)

        with self.assertRaises(ConflictError) as caught:
            await self.service.decide(
                self.session, FILED_REQUEST_ID, MANAGER, approve=False, comment="no"
            )

        self.assertIn("approved", str(caught.exception))
        self.assertEqual(
            self.requests.rows[FILED_REQUEST_ID].status, LeaveRequestStatus.APPROVED
        )


class TestExchange(LeaveRequestServiceTest):
    def setUp(self):
        super().setUp()
        self.holidays.list_by_year.return_value = [
            _holiday(datetime.date(2026, 10, 1), is_exchangeable=True),
            _holiday(datetime.date(2026, 10, 2), is_exchangeable=True),
            _holiday(datetime.date(2026, 10, 3), is_exchangeable=False),
        ]

    async def test_exchanging_two_exchangeable_days_is_credited_at_eight_each(self):
        request = await self._submit(
            request_type=LeaveRequestType.EXCHANGE,
            start_date=datetime.date(2026, 10, 1),
            end_date=datetime.date(2026, 10, 2),
        )

        self.assertEqual(request.hours, "16.00")

    async def test_a_day_that_cannot_be_exchanged_refuses_the_whole_request(self):
        """Not "credit the two that qualify": somebody would come in on the
        third day and find out afterwards that it bought nothing."""
        with self.assertRaises(ValueError) as caught:
            await self._submit(
                request_type=LeaveRequestType.EXCHANGE,
                start_date=datetime.date(2026, 10, 1),
                end_date=datetime.date(2026, 10, 3),
            )

        self.assertIn("2026-10-03", str(caught.exception))

    async def test_an_ordinary_working_day_cannot_be_exchanged(self):
        with self.assertRaises(ValueError):
            await self._submit(
                request_type=LeaveRequestType.EXCHANGE,
                start_date=datetime.date(2026, 10, 6),
                end_date=datetime.date(2026, 10, 6),
            )

    async def test_short_notice_refuses_an_exchange_outright(self):
        """Unlike leave, this one is hard: the office has to plan for somebody
        being in, and a mark on the request would not do that."""
        self._set_today(datetime.date(2026, 9, 29))

        with self.assertRaises(ValueError):
            await self._submit(
                request_type=LeaveRequestType.EXCHANGE,
                start_date=datetime.date(2026, 10, 1),
                end_date=datetime.date(2026, 10, 2),
            )

    async def test_enough_notice_lets_the_exchange_through(self):
        self._set_today(datetime.date(2026, 9, 20))

        request = await self._submit(
            request_type=LeaveRequestType.EXCHANGE,
            start_date=datetime.date(2026, 10, 1),
            end_date=datetime.date(2026, 10, 2),
        )

        self.assertEqual(request.status, LeaveRequestStatus.PENDING)


class TestDecisions(LeaveRequestServiceTest):
    async def _decide(self, approve=True, approver=MANAGER, comment=None):
        return await self.service.decide(
            self.session, STORED_REQUEST_ID, approver, approve=approve, comment=comment
        )

    async def test_approving_paid_leave_deducts_it_on_the_first_day(self):
        """One row for the request, dated where the leave starts, pointing back
        at it. Per-day rows would multiply the ledger and buy nothing: the
        request already says which days."""
        request = self._pending()

        await self._decide()

        self.assertEqual(request.status, LeaveRequestStatus.APPROVED)
        [row] = self._ledger_rows()
        self.assertEqual(row.entry_type, LeaveEntryType.LEAVE_DEDUCTION)
        self.assertEqual(row.hours, Decimal("-24.00"))
        self.assertEqual(row.effective_date, LEAVE_START)
        self.assertEqual(row.source_request_id, STORED_REQUEST_ID)
        self.assertEqual(row.user_id, EMPLOYEE)

    async def test_an_approval_is_attributed_to_the_approver(self):
        """Both the ledger row and the approval say who decided; the request
        read back says it too."""
        self._pending()

        decided = await self._decide()

        [row] = self._ledger_rows()
        self.assertEqual(row.created_by, MANAGER)
        approval = self._approval_for(STORED_REQUEST_ID)
        self.assertEqual(approval.status, ApprovalRequestStatus.APPROVED)
        self.assertEqual(approval.decided_by, MANAGER)
        self.assertEqual(decided.decided_by, MANAGER)
        self.assertEqual(decided.decided_at, approval.decided_at)

    async def test_deciding_holds_the_row_it_decides(self):
        """Read without the lock, a second decider sees the same pending row,
        passes the same check, and writes a second deduction onto a ledger that
        cannot be edited."""
        self._pending()

        await self._decide()

        self.requests.get_by_id.assert_any_await(
            self.session, STORED_REQUEST_ID, for_update=True
        )

    async def test_approving_an_exchange_credits_it(self):
        self._pending(
            request_type=LeaveRequestType.EXCHANGE,
            hours="16.00",
            end_date=datetime.date(2026, 8, 14),
        )

        await self._decide()

        [row] = self._ledger_rows()
        self.assertEqual(row.entry_type, LeaveEntryType.EXCHANGE_CREDIT)
        self.assertEqual(row.hours, Decimal("16.00"))

    async def test_approving_sick_leave_writes_no_row(self):
        request = self._pending(
            request_type=LeaveRequestType.SICK,
            hours="32.00",
            end_date=datetime.date(2026, 8, 18),
        )

        await self._decide()

        self.assertEqual(request.status, LeaveRequestStatus.APPROVED)
        self.assertEqual(self._ledger_rows(), [])

    async def test_rejecting_stores_the_reason_and_writes_no_row(self):
        request = self._pending()

        decided = await self._decide(approve=False, comment="  Team offsite.  ")

        self.assertEqual(request.status, LeaveRequestStatus.REJECTED)
        self.assertEqual(self._ledger_rows(), [])
        approval = self._approval_for(STORED_REQUEST_ID)
        self.assertEqual(approval.status, ApprovalRequestStatus.REJECTED)
        self.assertEqual(approval.decision_comment, "Team offsite.")
        self.assertEqual(decided.status, LeaveRequestStatus.REJECTED.value)
        self.assertEqual(decided.decision_comment, "Team offsite.")
        self.assertEqual(decided.decided_by, MANAGER)

    async def test_rejecting_without_a_reason_is_refused(self):
        """The employee is told why. A blank reason is no reason."""
        request = self._pending()

        for comment in (None, "   "):
            with self.subTest(comment=comment):
                with self.assertRaises(ValueError):
                    await self._decide(approve=False, comment=comment)

        self.assertEqual(request.status, LeaveRequestStatus.PENDING)
        self.assertEqual(
            self._approval_for(STORED_REQUEST_ID).status,
            ApprovalRequestStatus.PENDING,
        )
        self.session.commit.assert_not_awaited()

    async def test_only_the_named_approver_may_decide(self):
        """The approver was snapshotted at submission. Anybody else deciding
        would be an approval the record attributes to the wrong person."""
        request = self._pending()

        with self.assertRaises(PermissionError):
            await self._decide(approver=STRANGER)

        self.assertEqual(request.status, LeaveRequestStatus.PENDING)
        self.assertEqual(self._ledger_rows(), [])

    async def test_the_employee_cannot_decide_their_own_request(self):
        self._pending()

        with self.assertRaises(PermissionError):
            await self._decide(approver=EMPLOYEE)

    async def test_a_request_already_decided_cannot_be_decided_again(self):
        """Otherwise a second approval writes a second deduction."""
        request = self._pending()
        await self._decide()
        self.ledger.add_entries.reset_mock()

        with self.assertRaises(ConflictError) as caught:
            await self._decide()

        self.assertIn(
            f"Request {STORED_REQUEST_ID} is already approved", str(caught.exception)
        )
        self.assertEqual(request.status, LeaveRequestStatus.APPROVED)
        self.ledger.add_entries.assert_not_awaited()

    async def test_a_rejected_request_cannot_then_be_approved(self):
        request = self._pending()
        await self._decide(approve=False, comment="No cover.")

        with self.assertRaises(ConflictError):
            await self._decide()

        self.assertEqual(request.status, LeaveRequestStatus.REJECTED)
        self.assertEqual(self._ledger_rows(), [])

    async def test_deciding_something_that_does_not_exist_is_refused(self):
        with self.assertRaises(ValueError):
            await self._decide()

    async def test_an_approval_that_no_longer_holds_leaves_it_waiting(self):
        """The leave has started since it was filed: approving now would write
        the ledger backwards. Refused as a conflict the page can tell apart
        from somebody else having decided it."""
        request = self._pending()
        self._set_today(datetime.date(2026, 8, 14))

        with self.assertRaises(ConflictError) as caught:
            await self._decide()

        self.assertEqual(caught.exception.code, APPROVAL_CHECKS_FAILED)
        self.assertEqual(request.status, LeaveRequestStatus.PENDING)
        self.assertEqual(self._ledger_rows(), [])
        self.session.commit.assert_not_awaited()

    async def test_a_decision_is_committed_and_tells_the_employee(self):
        self._pending()

        await self._decide()

        self.session.commit.assert_awaited_once()
        kwargs = self.record_event.await_args.kwargs
        self.assertEqual(kwargs["event_type"], LeaveEvent.REQUEST_DECIDED)
        self.assertEqual(kwargs["subject_id"], STORED_REQUEST_ID)
        self.assertEqual(kwargs["actor_id"], MANAGER)
        self.assertEqual(kwargs["details"]["decision"], "approved")
        self.assertEqual(kwargs["details"]["requestId"], FIRST_APPROVAL_ID)

    async def test_filed_then_decided_end_to_end(self):
        """What submit raises is what decide finds."""
        filed = await self._submit()

        decided = await self.service.decide(
            self.session, filed.request_id, MANAGER, approve=True
        )

        self.assertEqual(decided.status, LeaveRequestStatus.APPROVED.value)
        [row] = self._ledger_rows()
        self.assertEqual(row.source_request_id, FILED_REQUEST_ID)


class TestWithdraw(LeaveRequestServiceTest):
    async def test_an_employee_may_take_back_a_request_nobody_has_decided(self):
        """No manager needed: nothing has reached the ledger."""
        request = self._pending()

        withdrawn = await self.service.withdraw(
            self.session, STORED_REQUEST_ID, EMPLOYEE
        )

        self.assertEqual(request.status, LeaveRequestStatus.WITHDRAWN)
        approval = self._approval_for(STORED_REQUEST_ID)
        self.assertEqual(approval.status, ApprovalRequestStatus.WITHDRAWN)
        self.assertEqual(approval.decided_by, EMPLOYEE)
        self.assertEqual(withdrawn.status, LeaveRequestStatus.WITHDRAWN.value)
        self.assertEqual(self._ledger_rows(), [])
        self.session.commit.assert_awaited_once()

    async def test_withdrawing_tells_the_manager(self):
        self._pending()

        await self.service.withdraw(self.session, STORED_REQUEST_ID, EMPLOYEE)

        kwargs = self.record_event.await_args.kwargs
        self.assertEqual(kwargs["event_type"], LeaveEvent.REQUEST_DECIDED)
        self.assertEqual(kwargs["details"]["decision"], "withdrawn")

    async def test_withdrawing_holds_the_row_too(self):
        """Withdrawing and deciding race against each other on one row."""
        self._pending()

        await self.service.withdraw(self.session, STORED_REQUEST_ID, EMPLOYEE)

        self.requests.get_by_id.assert_any_await(
            self.session, STORED_REQUEST_ID, for_update=True
        )

    async def test_only_its_owner_may_withdraw_it(self):
        request = self._pending()

        for somebody in (STRANGER, MANAGER):
            with self.subTest(somebody=somebody):
                with self.assertRaises(PermissionError):
                    await self.service.withdraw(
                        self.session, STORED_REQUEST_ID, somebody
                    )

        self.assertEqual(request.status, LeaveRequestStatus.PENDING)

    async def test_an_approved_request_cannot_be_withdrawn(self):
        """Approval is the end of the line. Putting the hours back is an admin
        adjustment with a note, not a transition."""
        request = self._pending()
        await self.service.decide(self.session, STORED_REQUEST_ID, MANAGER, True)

        with self.assertRaises(ConflictError):
            await self.service.withdraw(self.session, STORED_REQUEST_ID, EMPLOYEE)

        self.assertEqual(request.status, LeaveRequestStatus.APPROVED)

    async def test_sick_leave_approved_on_submission_cannot_be_withdrawn(self):
        await self._submit(request_type=LeaveRequestType.SICK)

        with self.assertRaises(ConflictError):
            await self.service.withdraw(self.session, FILED_REQUEST_ID, EMPLOYEE)

    async def test_withdrawing_something_that_does_not_exist_is_refused(self):
        with self.assertRaises(ValueError):
            await self.service.withdraw(self.session, STORED_REQUEST_ID, EMPLOYEE)


class TestLists(LeaveRequestServiceTest):
    def setUp(self):
        super().setUp()
        self.requests.list_for_user = AsyncMock(return_value=[])
        self.requests.list_for_approver = AsyncMock(return_value=[])

    def _row(self, request_id=STORED_REQUEST_ID, user_id=EMPLOYEE):
        request = _stored_request(request_id=request_id)
        request.user_id = user_id
        request.is_late_notice = True
        return request

    def _decided(self, request, status, comment=None):
        """An approval on file for a request, closed by its manager."""
        row = self.approval_requests.add(
            action=LEAVE_APPROVAL,
            target_type=LEAVE_REQUEST_SUBJECT,
            target_id=str(request.leave_request_id),
            payload={},
            reason=None,
            raised_by=EMPLOYEE,
            reviewer_id=MANAGER,
            status=status,
        )
        row.decided_by = (
            EMPLOYEE if status is ApprovalRequestStatus.WITHDRAWN else MANAGER
        )
        row.decided_at = datetime.datetime(
            2026, 8, 7, 14, 0, tzinfo=datetime.timezone.utc
        )
        row.decision_comment = comment
        return row

    async def test_a_persons_own_requests_carry_their_hours_as_text(self):
        """Never a float: the encoder turns a Decimal into one, and 78.46 comes
        back as 78.45999999999999."""
        self.requests.list_for_user.return_value = [self._row()]

        requests = await self.service.list_own(self.session, EMPLOYEE)

        self.assertEqual(requests[0].hours, "24.00")
        self.assertEqual(requests[0].request_id, 501)
        self.assertTrue(requests[0].is_late_notice)

    async def test_the_approver_queue_names_the_person_asking(self):
        """A queue of user ids is unusable. The name is resolved the same way
        every other view of somebody else's name resolves it."""
        person = MagicMock()
        person.user_id = EMPLOYEE
        person.first_name = "Ann"
        person.last_name = "Employee"
        person.preferred_name = None
        self.users.get_all_by_ids.return_value = [person]
        self.requests.list_for_approver.return_value = [self._row()]

        queue = await self.service.list_for_approver(self.session, MANAGER)

        self.assertEqual(queue[0].employee_name, "Ann Employee")

    async def test_the_queue_holds_every_status_not_only_what_is_waiting(self):
        """Being an approver is read off this list: nobody carries a manager
        flag, so the entry point exists exactly when somebody has filed against
        you. Narrowing this to pending would take the entry away the moment a
        manager finished deciding, and with it any way to look up what they
        decided."""
        await self.service.list_for_approver(self.session, MANAGER)

        self.assertEqual(
            self.requests.list_for_approver.await_args.args[2],
            list(LeaveRequestStatus),
        )

    async def test_a_decided_request_stays_in_the_approver_list(self):
        row = self._row()
        row.status = LeaveRequestStatus.APPROVED
        self.requests.list_for_approver.return_value = [row]

        listed = await self.service.list_for_approver(self.session, MANAGER)

        self.assertEqual([entry.status for entry in listed], ["approved"])

    async def test_the_queue_carries_the_ldap_off_the_corporate_address(self):
        """Azure knows people by ldap and purrf knows them by account; the
        corporate address is the whole of the join, so the ldap is read off it
        rather than stored a second time."""
        self.requests.list_for_approver.return_value = [self._row()]
        self.emails.get_emails_by_user_ids.return_value = {
            EMPLOYEE: ["ann.personal@gmail.com", "aemployee@circlecat.org"]
        }

        queue = await self.service.list_for_approver(self.session, MANAGER)

        self.assertEqual(queue[0].employee_ldap, "aemployee")

    async def test_an_ldap_that_cannot_be_resolved_does_not_break_the_queue(self):
        """Same discipline as the name: somebody with no corporate address is
        shown without one rather than taking a manager's whole queue down."""
        self.requests.list_for_approver.return_value = [self._row()]
        self.emails.get_emails_by_user_ids.return_value = {
            EMPLOYEE: ["ann.personal@gmail.com"]
        }

        queue = await self.service.list_for_approver(self.session, MANAGER)

        self.assertIsNone(queue[0].employee_ldap)

    async def test_two_corporate_addresses_resolve_the_same_way_every_time(self):
        """The directory join says this cannot happen. If it does, two reads of
        the same account must still agree."""
        self.requests.list_for_approver.return_value = [self._row()]
        self.emails.get_emails_by_user_ids.return_value = {
            EMPLOYEE: ["zzz@circlecat.org", "aaa@circlecat.org"]
        }

        queue = await self.service.list_for_approver(self.session, MANAGER)

        self.assertEqual(queue[0].employee_ldap, "aaa")

    async def test_a_pending_request_says_where_the_balance_lands(self):
        """The number an approver is actually deciding on. Paid leave spends
        the balance, so approving takes it down by the hours asked for."""
        self.requests.list_for_approver.return_value = [self._row()]
        self.ledger.balances_by_user_ids.return_value = {EMPLOYEE: Decimal("30.00")}

        queue = await self.service.list_for_approver(self.session, MANAGER)

        self.assertEqual(queue[0].balance_before, "30.00")
        self.assertEqual(queue[0].balance_after, "6.00")

    async def test_an_exchange_puts_hours_back_rather_than_taking_them(self):
        row = self._row()
        row.type = LeaveRequestType.EXCHANGE
        self.requests.list_for_approver.return_value = [row]
        self.ledger.balances_by_user_ids.return_value = {EMPLOYEE: Decimal("30.00")}

        queue = await self.service.list_for_approver(self.session, MANAGER)

        self.assertEqual(queue[0].balance_after, "54.00")

    async def test_sick_leave_leaves_the_balance_where_it_was(self):
        """It has no allowance and deducts nothing, so approving moves nothing
        -- and the pair of numbers has to say so rather than imply a cost."""
        row = self._row()
        row.type = LeaveRequestType.SICK
        self.requests.list_for_approver.return_value = [row]
        self.ledger.balances_by_user_ids.return_value = {EMPLOYEE: Decimal("30.00")}

        queue = await self.service.list_for_approver(self.session, MANAGER)

        self.assertEqual(queue[0].balance_before, "30.00")
        self.assertEqual(queue[0].balance_after, "30.00")

    async def test_the_balance_may_land_below_zero(self):
        """An L1 has no entitlement and may still take paid leave, so this is
        a real answer rather than something to clamp."""
        self.requests.list_for_approver.return_value = [self._row()]
        self.ledger.balances_by_user_ids.return_value = {EMPLOYEE: Decimal("12.00")}

        queue = await self.service.list_for_approver(self.session, MANAGER)

        self.assertEqual(queue[0].balance_after, "-12.00")

    async def test_somebody_with_no_ledger_rows_starts_from_zero(self):
        self.requests.list_for_approver.return_value = [self._row()]
        self.ledger.balances_by_user_ids.return_value = {}

        queue = await self.service.list_for_approver(self.session, MANAGER)

        self.assertEqual(queue[0].balance_before, "0.00")
        self.assertEqual(queue[0].balance_after, "-24.00")

    async def test_a_decided_request_carries_no_hypothetical_balance(self):
        """The ledger has already moved, so "where would this land" has no
        answer -- and a number here would be read as the balance today."""
        row = self._row()
        row.status = LeaveRequestStatus.APPROVED
        self.requests.list_for_approver.return_value = [row]
        self.ledger.balances_by_user_ids.return_value = {EMPLOYEE: Decimal("30.00")}

        queue = await self.service.list_for_approver(self.session, MANAGER)

        self.assertIsNone(queue[0].balance_before)
        self.assertIsNone(queue[0].balance_after)

    async def test_a_request_says_how_much_notice_it_owed(self):
        """The flag alone says only "not enough". What the rule asked for is
        the number a reader needs, and computing it in the browser would put
        the notice rule in two places."""
        self.requests.list_for_approver.return_value = [self._row()]

        queue = await self.service.list_for_approver(self.session, MANAGER)

        # 24 hours is three days, and the rule asks twice the days.
        self.assertEqual(queue[0].required_notice_workdays, 6)

    async def test_part_of_a_day_still_owes_a_whole_days_notice(self):
        """Four hours off and eight ask for the same notice: the day has to be
        covered either way."""
        row = self._row()
        row.hours = Decimal("4.00")
        self.requests.list_for_approver.return_value = [row]

        queue = await self.service.list_for_approver(self.session, MANAGER)

        self.assertEqual(queue[0].required_notice_workdays, 2)

    async def test_sick_leave_owes_no_notice_at_all(self):
        """Nobody schedules illness, so there is no requirement to state."""
        row = self._row()
        row.type = LeaveRequestType.SICK
        self.requests.list_for_approver.return_value = [row]

        queue = await self.service.list_for_approver(self.session, MANAGER)

        self.assertIsNone(queue[0].required_notice_workdays)

    async def test_your_own_list_states_the_same_requirement(self):
        """Two views of one request must not disagree about what it owed."""
        self.requests.list_for_user.return_value = [self._row()]

        own = await self.service.list_own(self.session, EMPLOYEE)

        self.assertEqual(own[0].required_notice_workdays, 6)

    async def test_a_name_that_cannot_be_resolved_does_not_break_the_queue(self):
        """A deleted account should not take a manager's whole queue down."""
        self.requests.list_for_approver.return_value = [self._row()]

        queue = await self.service.list_for_approver(self.session, MANAGER)

        self.assertIsNone(queue[0].employee_name)

    async def test_your_own_list_says_who_decided_when_and_why(self):
        """Read off the approval: the request row no longer carries them."""
        row = self._row()
        row.status = LeaveRequestStatus.REJECTED
        approval = self._decided(
            row, ApprovalRequestStatus.REJECTED, comment="No cover that week."
        )
        self.requests.list_for_user.return_value = [row]

        [own] = await self.service.list_own(self.session, EMPLOYEE)

        self.assertEqual(own.decided_by, MANAGER)
        self.assertEqual(own.decided_at, approval.decided_at)
        self.assertEqual(own.decision_comment, "No cover that week.")
        dumped = own.model_dump(by_alias=True)
        self.assertEqual(dumped["decidedBy"], MANAGER)
        self.assertEqual(dumped["decisionComment"], "No cover that week.")
        self.assertIn("decidedAt", dumped)

    async def test_the_approver_queue_says_who_decided_when_and_why(self):
        row = self._row()
        row.status = LeaveRequestStatus.APPROVED
        approval = self._decided(row, ApprovalRequestStatus.APPROVED, comment="Enjoy.")
        self.requests.list_for_approver.return_value = [row]

        [listed] = await self.service.list_for_approver(self.session, MANAGER)

        self.assertEqual(listed.decided_by, MANAGER)
        self.assertEqual(listed.decided_at, approval.decided_at)
        self.assertEqual(listed.decision_comment, "Enjoy.")

    async def test_each_request_carries_its_own_approval(self):
        """Two requests, two approvals: neither borrows the other's decision."""
        first = self._row(request_id=501)
        first.status = LeaveRequestStatus.REJECTED
        second = self._row(request_id=502)
        self._decided(first, ApprovalRequestStatus.REJECTED, comment="Clash.")
        self.approval_requests.add(
            action=LEAVE_APPROVAL,
            target_type=LEAVE_REQUEST_SUBJECT,
            target_id="502",
            payload={},
            reason=None,
            raised_by=EMPLOYEE,
            reviewer_id=MANAGER,
            status=ApprovalRequestStatus.PENDING,
        )
        self.requests.list_for_user.return_value = [first, second]

        own = await self.service.list_own(self.session, EMPLOYEE)

        self.assertEqual(
            [(r.request_id, r.decision_comment, r.decided_by) for r in own],
            [(501, "Clash.", MANAGER), (502, None, None)],
        )

    async def test_a_withdrawn_request_names_its_owner_as_who_closed_it(self):
        row = self._row()
        row.status = LeaveRequestStatus.WITHDRAWN
        self._decided(row, ApprovalRequestStatus.WITHDRAWN)
        self.requests.list_for_user.return_value = [row]

        [own] = await self.service.list_own(self.session, EMPLOYEE)

        self.assertEqual(own.decided_by, EMPLOYEE)
        self.assertIsNone(own.decision_comment)

    async def test_sick_leave_approved_on_filing_was_decided_when_filed(self):
        """No approval behind it: decided when it was filed, by nobody."""
        row = self._row()
        row.type = LeaveRequestType.SICK
        row.status = LeaveRequestStatus.APPROVED
        self.requests.list_for_user.return_value = [row]

        [own] = await self.service.list_own(self.session, EMPLOYEE)

        self.assertIsNone(own.decided_by)
        self.assertEqual(own.decided_at, FILED_AT)
        self.assertIsNone(own.decision_comment)

    async def test_a_waiting_paid_request_is_judged_against_the_balance_now(self):
        """The mark filed with it said the balance covered it; the hours held
        by everything still waiting say otherwise today."""
        row = self._row()
        row.is_overdraft = False
        self.requests.list_for_approver.return_value = [row]
        self.ledger.balances_by_user_ids.return_value = {EMPLOYEE: Decimal("30.00")}
        self.requests.sum_pending_paid_hours.return_value = Decimal("40.00")

        [listed] = await self.service.list_for_approver(self.session, MANAGER)

        self.assertTrue(listed.is_overdraft)
        self.requests.sum_pending_paid_hours.assert_awaited_with(self.session, EMPLOYEE)

    async def test_a_stale_overdraft_mark_clears_once_the_balance_covers_it(self):
        row = self._row()
        row.is_overdraft = True
        self.requests.list_for_approver.return_value = [row]
        self.ledger.balances_by_user_ids.return_value = {EMPLOYEE: Decimal("40.00")}
        self.requests.sum_pending_paid_hours.return_value = Decimal("40.00")

        [listed] = await self.service.list_for_approver(self.session, MANAGER)

        self.assertFalse(listed.is_overdraft)

    async def test_a_decided_request_keeps_the_mark_it_was_decided_on(self):
        row = self._row()
        row.status = LeaveRequestStatus.APPROVED
        row.is_overdraft = True
        self._decided(row, ApprovalRequestStatus.APPROVED)
        self.requests.list_for_approver.return_value = [row]
        self.ledger.balances_by_user_ids.return_value = {EMPLOYEE: Decimal("500.00")}

        [listed] = await self.service.list_for_approver(self.session, MANAGER)

        self.assertTrue(listed.is_overdraft)

    async def test_a_waiting_exchange_keeps_its_stored_mark(self):
        """It spends nothing, so there is nothing to judge again."""
        row = self._row()
        row.type = LeaveRequestType.EXCHANGE
        row.is_overdraft = False
        self.requests.list_for_approver.return_value = [row]
        self.ledger.balances_by_user_ids.return_value = {EMPLOYEE: Decimal("0.00")}
        self.requests.sum_pending_paid_hours.return_value = Decimal("40.00")

        [listed] = await self.service.list_for_approver(self.session, MANAGER)

        self.assertFalse(listed.is_overdraft)

    async def test_your_own_list_shows_the_stored_mark(self):
        """Only the approver's queue works it out again."""
        row = self._row()
        row.is_overdraft = False
        self.requests.list_for_user.return_value = [row]
        self.ledger.balance.return_value = Decimal("0.00")
        self.requests.sum_pending_paid_hours.return_value = Decimal("40.00")

        [own] = await self.service.list_own(self.session, EMPLOYEE)

        self.assertFalse(own.is_overdraft)


class TestCoverage(LeaveRequestServiceTest):
    """Whether the leave system has anything to do with one account.

    Nothing in the feature should offer somebody a screen it cannot serve, and
    nothing should tell somebody outside the population that they hold a
    balance of zero -- that reads as an entitlement of nothing rather than as
    "this does not apply to you".
    """

    async def test_somebody_the_nightly_sync_knows_is_covered(self):
        covered = await self.service.coverage(self.session, EMPLOYEE)

        self.assertTrue(covered)

    async def test_somebody_the_sync_has_never_seen_is_not_covered(self):
        self.redis_client.hgetall.return_value = {}
        self.ledger.balances_by_user_ids.return_value = {}

        covered = await self.service.coverage(self.session, EMPLOYEE)

        self.assertFalse(covered)

    async def test_a_ledger_row_covers_somebody_the_sync_has_dropped(self):
        """Somebody who has left the population keeps their history. Their
        profile is deleted the next night, and hiding the record with it would
        make the hours they were granted unaccountable."""
        self.redis_client.hgetall.return_value = {}
        self.ledger.balances_by_user_ids.return_value = {EMPLOYEE: Decimal("8.00")}

        covered = await self.service.coverage(self.session, EMPLOYEE)

        self.assertTrue(covered)

    async def test_a_zero_balance_still_counts_as_a_row(self):
        """A balance summing to zero is not an absent one. Falling back to the
        figure rather than to the presence of rows would drop exactly the
        people whose credits and deductions cancel out."""
        self.redis_client.hgetall.return_value = {}
        self.ledger.balances_by_user_ids.return_value = {EMPLOYEE: Decimal("0.00")}

        covered = await self.service.coverage(self.session, EMPLOYEE)

        self.assertTrue(covered)

    async def test_an_account_with_no_corporate_address_is_not_covered(self):
        """The corporate address is the whole of the join onto Azure, so
        without one there is no profile to find."""
        self.emails.list_by_user_id.return_value = [_email("ann@gmail.com")]
        self.ledger.balances_by_user_ids.return_value = {}

        covered = await self.service.coverage(self.session, EMPLOYEE)

        self.assertFalse(covered)

    async def test_the_cache_is_not_consulted_without_an_ldap(self):
        """There is no key to ask about, so the round trip is skipped."""
        self.emails.list_by_user_id.return_value = [_email("ann@gmail.com")]
        self.ledger.balances_by_user_ids.return_value = {}

        await self.service.coverage(self.session, EMPLOYEE)

        self.redis_client.hgetall.assert_not_called()

    async def test_no_corporate_address_but_a_ledger_row_is_still_covered(self):
        self.emails.list_by_user_id.return_value = [_email("ann@gmail.com")]
        self.ledger.balances_by_user_ids.return_value = {EMPLOYEE: Decimal("8.00")}

        covered = await self.service.coverage(self.session, EMPLOYEE)

        self.assertTrue(covered)


class TestStanding(LeaveRequestServiceTest):
    """The three figures a dashboard answers "what can I spend" with."""

    async def test_available_holds_back_what_is_already_requested(self):
        """Same definition the overdraft mark uses, so a card cannot say
        somebody can afford leave that filing would then flag."""
        self.ledger.balance.return_value = Decimal("80.00")
        self.requests.sum_pending_paid_hours.return_value = Decimal("24.00")

        standing = await self.service.standing(self.session, EMPLOYEE)

        self.assertTrue(standing.is_covered)
        self.assertEqual(standing.available, Decimal("56.00"))
        self.assertEqual(standing.pending, Decimal("24.00"))

    async def test_used_is_shown_as_spent_though_stored_negative(self):
        self.ledger.balance.return_value = Decimal("56.00")
        self.ledger.sum_deductions_for_year.return_value = Decimal("-24.00")

        standing = await self.service.standing(self.session, EMPLOYEE)

        self.assertEqual(standing.used, Decimal("24.00"))

    async def test_used_covers_this_year_only(self):
        """A figure summed across years would say somebody spent this year
        what they spent over their whole employment."""
        self.ledger.balance.return_value = Decimal("56.00")

        await self.service.standing(self.session, EMPLOYEE)

        self.assertEqual(
            self.ledger.sum_deductions_for_year.await_args.args[2], TODAY.year
        )

    async def test_available_may_be_negative(self):
        """An L1 has no entitlement and may still take paid leave."""
        self.ledger.balance.return_value = Decimal("0.00")
        self.requests.sum_pending_paid_hours.return_value = Decimal("8.00")

        standing = await self.service.standing(self.session, EMPLOYEE)

        self.assertEqual(standing.available, Decimal("-8.00"))

    async def test_nothing_is_quoted_to_somebody_the_feature_misses(self):
        """Zero would read as an entitlement of nothing rather than as a
        feature with nothing to do with them."""
        self.redis_client.hgetall.return_value = {}
        self.ledger.balances_by_user_ids.return_value = {}

        standing = await self.service.standing(self.session, EMPLOYEE)

        self.assertFalse(standing.is_covered)
        self.assertIsNone(standing.available)
        self.assertIsNone(standing.pending)
        self.assertIsNone(standing.used)

    async def test_no_ledger_is_read_for_somebody_it_misses(self):
        """Nothing to compute, so nothing is asked."""
        self.redis_client.hgetall.return_value = {}
        self.ledger.balances_by_user_ids.return_value = {}
        self.ledger.balance.reset_mock()

        await self.service.standing(self.session, EMPLOYEE)

        self.ledger.balance.assert_not_awaited()


if __name__ == "__main__":
    main()
