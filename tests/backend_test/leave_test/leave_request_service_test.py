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

from backend.common.leave_enums import (
    LeaveEntryType,
    LeaveRequestStatus,
    LeaveRequestType,
)
from backend.entity.leave_holiday_entity import LeaveHolidayEntity
from backend.leave.leave_participants import ResolvedParticipants
from backend.leave.leave_request_service import LeaveRequestService

TODAY = datetime.date(2026, 8, 5)
# Thursday to Saturday, three working days.
LEAVE_START = datetime.date(2026, 8, 13)
LEAVE_END = datetime.date(2026, 8, 15)

EMPLOYEE = 10
MANAGER = 20


def _holiday(day, is_exchangeable=False, name="Company holiday"):
    return LeaveHolidayEntity(
        year=day.year, date=day, name=name, is_exchangeable=is_exchangeable
    )


class LeaveRequestServiceTest(IsolatedAsyncioTestCase):
    def setUp(self):
        self.logger = MagicMock()
        self.requests = MagicMock()
        self.requests.add = AsyncMock(side_effect=lambda session, request: request)
        self.requests.list_overlapping = AsyncMock(return_value=[])
        self.requests.sum_pending_paid_hours = AsyncMock(return_value=Decimal("0.00"))
        self.requests.get_by_id = AsyncMock()
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
        self.users = MagicMock()
        self.users.get_all_by_ids = AsyncMock(return_value=[])
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
        )
        clock = patch("backend.leave.leave_request_service.business_today")
        self.business_today = clock.start()
        self.business_today.return_value = TODAY
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


def _email(address):
    row = MagicMock()
    row.email = address
    return row


class TestSubmit(LeaveRequestServiceTest):
    async def test_a_request_is_stored_pending_with_its_hours(self):
        request = await self._submit()

        self.assertEqual(request.status, LeaveRequestStatus.PENDING)
        self.assertEqual(request.hours, Decimal("24.00"))
        self.assertEqual(request.user_id, EMPLOYEE)
        self.session.commit.assert_awaited_once()

    async def test_the_approver_is_the_manager_azure_names_today(self):
        """A snapshot, not a lookup at decision time: changing manager later
        must not repoint a request somebody has already decided."""
        request = await self._submit()

        self.assertEqual(request.approver_user_id, MANAGER)

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

    async def test_a_manager_with_no_purrf_account_cannot_be_an_approver(self):
        self.resolver.resolve.return_value = ResolvedParticipants(
            by_ldap={}, unresolved=("bob",), not_internal=()
        )

        with self.assertRaises(ValueError):
            await self._submit()

    async def test_somebody_outside_the_leave_system_cannot_submit(self):
        self.redis_client.hgetall.return_value = {}

        with self.assertRaises(ValueError):
            await self._submit()

    async def test_somebody_with_no_corporate_address_cannot_submit(self):
        """Their Azure profile is found by ldap, and the corporate address is
        the only thing that ties a purrf account to one."""
        self.emails.list_by_user_id.return_value = [_email("ann@gmail.com")]

        with self.assertRaises(ValueError):
            await self._submit()


class TestNoticeAndOverdraft(LeaveRequestServiceTest):
    async def test_enough_notice_leaves_the_flag_clear(self):
        """Three days off asked for on 5 August: six working days, exactly the
        six they need."""
        request = await self._submit()

        self.assertFalse(request.is_late_notice)

    async def test_a_day_less_notice_sets_the_flag_but_still_submits(self):
        """A soft mark. The manager decides; the system does not refuse."""
        self.business_today.return_value = datetime.date(2026, 8, 6)

        request = await self._submit()

        self.assertTrue(request.is_late_notice)
        self.assertEqual(request.status, LeaveRequestStatus.PENDING)

    async def test_sick_leave_is_never_late(self):
        """Nobody schedules illness, and a mark nobody can act on is noise."""
        self.business_today.return_value = datetime.date(2026, 8, 12)

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
        exactly is approved. decided_by stays empty: nobody decided it."""
        request = await self._submit(request_type=LeaveRequestType.SICK)

        self.assertEqual(request.status, LeaveRequestStatus.APPROVED)
        self.assertIsNone(request.decided_by)
        self.assertIsNotNone(request.decided_at)

    async def test_a_fourth_day_puts_it_in_front_of_the_manager(self):
        """24h exactly is approved on submission; the next working day past it
        is not. 13 to 18 August spans four working days -- the 16th is a Sunday
        and the 17th a Monday, so they do not count towards the hours either."""
        four_days = await self._submit(
            request_type=LeaveRequestType.SICK,
            start_date=LEAVE_START,
            end_date=datetime.date(2026, 8, 18),
        )

        self.assertEqual(four_days.hours, Decimal("32.00"))
        self.assertEqual(four_days.status, LeaveRequestStatus.PENDING)
        self.assertIsNone(four_days.decided_at)

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

        self.assertEqual(request.hours, Decimal("16.00"))

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
        self.business_today.return_value = datetime.date(2026, 9, 29)

        with self.assertRaises(ValueError):
            await self._submit(
                request_type=LeaveRequestType.EXCHANGE,
                start_date=datetime.date(2026, 10, 1),
                end_date=datetime.date(2026, 10, 2),
            )

    async def test_enough_notice_lets_the_exchange_through(self):
        self.business_today.return_value = datetime.date(2026, 9, 20)

        request = await self._submit(
            request_type=LeaveRequestType.EXCHANGE,
            start_date=datetime.date(2026, 10, 1),
            end_date=datetime.date(2026, 10, 2),
        )

        self.assertEqual(request.status, LeaveRequestStatus.PENDING)


class TestDecisions(LeaveRequestServiceTest):
    def _pending(self, request_type=LeaveRequestType.PAID, hours="24.00"):
        request = MagicMock()
        request.leave_request_id = 501
        request.user_id = EMPLOYEE
        request.approver_user_id = MANAGER
        request.type = request_type
        request.status = LeaveRequestStatus.PENDING
        request.hours = Decimal(hours)
        request.start_date = LEAVE_START
        request.end_date = LEAVE_END
        request.decided_by = None
        self.requests.get_by_id.return_value = request
        return request

    def _ledger_rows(self):
        return [
            entry
            for call in self.ledger.add_entries.await_args_list
            for entry in call.args[1]
        ]

    async def test_approving_paid_leave_deducts_it_on_the_first_day(self):
        """One row for the request, dated where the leave starts, pointing back
        at it. Per-day rows would multiply the ledger and buy nothing: the
        request already says which days."""
        request = self._pending()

        await self.service.decide(self.session, 501, MANAGER, approve=True)

        self.assertEqual(request.status, LeaveRequestStatus.APPROVED)
        self.assertEqual(request.decided_by, MANAGER)
        row = self._ledger_rows()[0]
        self.assertEqual(row.entry_type, LeaveEntryType.LEAVE_DEDUCTION)
        self.assertEqual(row.hours, Decimal("-24.00"))
        self.assertEqual(row.effective_date, LEAVE_START)
        self.assertEqual(row.source_request_id, 501)
        self.assertEqual(row.created_by, MANAGER)

    async def test_approving_an_exchange_credits_it(self):
        self._pending(request_type=LeaveRequestType.EXCHANGE, hours="16.00")

        await self.service.decide(self.session, 501, MANAGER, approve=True)

        row = self._ledger_rows()[0]
        self.assertEqual(row.entry_type, LeaveEntryType.EXCHANGE_CREDIT)
        self.assertEqual(row.hours, Decimal("16.00"))

    async def test_approving_sick_leave_writes_no_row(self):
        self._pending(request_type=LeaveRequestType.SICK, hours="32.00")

        await self.service.decide(self.session, 501, MANAGER, approve=True)

        self.assertEqual(self._ledger_rows(), [])

    async def test_rejecting_writes_no_row(self):
        request = self._pending()

        await self.service.decide(self.session, 501, MANAGER, approve=False)

        self.assertEqual(request.status, LeaveRequestStatus.REJECTED)
        self.assertEqual(self._ledger_rows(), [])

    async def test_only_the_named_approver_may_decide(self):
        """The approver was snapshotted at submission. Anybody else deciding
        would be an approval the record attributes to the wrong person."""
        self._pending()

        with self.assertRaises(PermissionError):
            await self.service.decide(self.session, 501, 99, approve=True)

        self.assertEqual(self._ledger_rows(), [])

    async def test_a_request_already_decided_cannot_be_decided_again(self):
        """Otherwise a second approval writes a second deduction."""
        request = self._pending()
        request.status = LeaveRequestStatus.APPROVED

        with self.assertRaises(ValueError):
            await self.service.decide(self.session, 501, MANAGER, approve=True)

        self.assertEqual(self._ledger_rows(), [])

    async def test_deciding_something_that_does_not_exist_is_refused(self):
        self.requests.get_by_id.return_value = None

        with self.assertRaises(ValueError):
            await self.service.decide(self.session, 501, MANAGER, approve=True)

    async def test_a_decision_is_committed(self):
        self._pending()

        await self.service.decide(self.session, 501, MANAGER, approve=True)

        self.session.commit.assert_awaited_once()


class TestWithdraw(LeaveRequestServiceTest):
    def _pending(self):
        request = MagicMock()
        request.leave_request_id = 501
        request.user_id = EMPLOYEE
        request.approver_user_id = MANAGER
        request.type = LeaveRequestType.PAID
        request.status = LeaveRequestStatus.PENDING
        request.hours = Decimal("24.00")
        self.requests.get_by_id.return_value = request
        return request

    async def test_an_employee_may_take_back_a_request_nobody_has_decided(self):
        """No manager needed: nothing has reached the ledger."""
        request = self._pending()

        await self.service.withdraw(self.session, 501, EMPLOYEE)

        self.assertEqual(request.status, LeaveRequestStatus.WITHDRAWN)
        self.session.commit.assert_awaited_once()

    async def test_only_its_owner_may_withdraw_it(self):
        self._pending()

        with self.assertRaises(PermissionError):
            await self.service.withdraw(self.session, 501, 99)

    async def test_an_approved_request_cannot_be_withdrawn(self):
        """Approval is the end of the line. Putting the hours back is an admin
        adjustment with a note, not a transition."""
        request = self._pending()
        request.status = LeaveRequestStatus.APPROVED

        with self.assertRaises(ValueError):
            await self.service.withdraw(self.session, 501, EMPLOYEE)

        self.assertEqual(request.status, LeaveRequestStatus.APPROVED)


class TestLists(LeaveRequestServiceTest):
    def setUp(self):
        super().setUp()
        self.requests.list_for_user = AsyncMock(return_value=[])
        self.requests.list_for_approver = AsyncMock(return_value=[])

    def _row(self, request_id=501, user_id=EMPLOYEE):
        request = MagicMock()
        request.leave_request_id = request_id
        request.user_id = user_id
        request.type = LeaveRequestType.PAID
        request.status = LeaveRequestStatus.PENDING
        request.start_date = LEAVE_START
        request.end_date = LEAVE_END
        request.start_time = None
        request.end_time = None
        request.hours = Decimal("24.00")
        request.is_overdraft = False
        request.is_late_notice = True
        request.reason = "Holiday"
        request.approver_user_id = MANAGER
        request.decided_by = None
        request.decided_at = None
        return request

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


if __name__ == "__main__":
    main()
