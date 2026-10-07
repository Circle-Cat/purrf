"""Submitting, withdrawing and deciding leave and exchange requests.

Three checks refuse a submission outright, and each exists because what it
prevents is silent. Leave dated in the past would rewrite the ledger behind a
year the annual close has already settled. A day already claimed by another
request would be deducted twice, and by the time anybody noticed both
deductions would be ledger rows that cannot be edited. A year with no company
holidays entered would have its hours computed against an empty calendar and
quietly come out too high.

Nothing reaches the ledger until somebody decides. The ledger records facts, and
a request nobody has decided is not one yet -- which is also why a pending
request's hours are held back from the balance separately.

Approval is the end of the line. There is no cancelling an approved request:
somebody who does not take leave they had approved has spent the hours, and
putting them back is an admin adjustment carrying a note.

Deciding and withdrawing run through the shared approval flow (see
leave_request_handler): the approval record says who decided, when and why,
and the request's own status says where it is.
"""

import datetime
import json
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.constants import INTERNAL_GOOGLE_ACCOUNT_DOMAIN
from backend.common.exceptions import ConflictError
from backend.common.leave_enums import (
    LEAVE_APPROVAL,
    LeaveEntryType,
    LeaveRequestStatus,
    LeaveRequestType,
)
from backend.common.name_utils import user_display_name
from backend.dto.leave_request_dto import LeaveRequestDto
from backend.entity.leave_ledger_entity import LeaveLedgerEntity
from backend.entity.leave_request_entity import LeaveRequestEntity
from backend.leave.leave_clock import business_today
from backend.leave.leave_workdays import (
    request_hours,
    required_notice_workdays,
    workdays_before,
)

LEAVE_EMPLOYMENT_KEY = "leave:employment"

NO_HOURS = Decimal("0.00")

# "Over three days, talk to your manager" -- so three days exactly does not need
# one. Measured in hours, through the same working-day count as a deduction.
SICK_AUTO_APPROVE_HOURS = Decimal("24.00")


def _balance_delta(request_type: LeaveRequestType, hours: Decimal) -> Decimal:
    """What approving a request of this type does to a balance.

    Three answers, not two: an exchange credits the hours, paid leave spends
    them, and sick leave moves the balance not at all -- it has no allowance
    and deducts nothing. The ledger row an approval writes and the figure an
    approver is shown both come from here, so the screen cannot promise one
    thing and the ledger record another.

    Args:
        request_type: Which kind of request.
        hours: The hours it covers, always positive.

    Returns:
        The signed change, zero for sick leave.
    """
    if request_type is LeaveRequestType.SICK:
        return NO_HOURS
    if request_type is LeaveRequestType.EXCHANGE:
        return hours
    return -hours


@dataclass(frozen=True)
class LeaveStanding:
    """Whether leave applies to somebody, and what they can spend.

    Every figure is None when it does not apply. Zero is a real balance and
    would be read as one.
    """

    is_covered: bool
    available: Decimal | None
    pending: Decimal | None
    used: Decimal | None


def _ldap_from_addresses(addresses) -> str | None:
    """The Azure ldap an account carries, or None if it carries none.

    Azure knows people by ldap and purrf knows them by account; the corporate
    address is the whole of the join, so the ldap is read off it rather than
    stored a second time. Sorted, so that an account somehow holding two
    corporate addresses still reads the same way every time -- the directory
    join says that cannot happen, and if it does the answer must at least not
    move around between requests.

    Args:
        addresses: The account's email addresses, in any order.

    Returns:
        The local part of its corporate address, or None.
    """
    for address in sorted(addresses):
        if address.endswith(INTERNAL_GOOGLE_ACCOUNT_DOMAIN):
            return address.split("@")[0]
    return None


async def load_calendar(
    session: AsyncSession,
    leave_holiday_repository,
    today: datetime.date,
    start_date: datetime.date,
    end_date: datetime.date,
) -> tuple[frozenset[datetime.date], frozenset[datetime.date]]:
    """Company holidays covering a request and its notice window.

    Every year the request itself touches must be entered. Without it the
    hours would be computed against a year with no holidays in it and
    quietly come out too high.

    The notice window can reach back into an earlier year -- asking in
    December for leave in January -- and that year is not required to be
    entered. A missing calendar there makes the notice count generous
    rather than wrong, which is the harmless direction.

    Args:
        session: Active async session.
        leave_holiday_repository (LeaveHolidayRepository): The calendar.
        today: The business day the request is judged on.
        start_date: First day of the leave.
        end_date: Last day of the leave.

    Returns:
        All the holiday dates, and the subset that may be exchanged.

    Raises:
        ValueError: A year the request covers has no holidays entered.
    """
    holidays: set[datetime.date] = set()
    exchangeable: set[datetime.date] = set()
    for year in range(min(today.year, start_date.year), end_date.year + 1):
        rows = await leave_holiday_repository.list_by_year(session, year)
        if not rows and start_date.year <= year <= end_date.year:
            raise ValueError(
                f"The company holidays for {year} have not been entered "
                "yet, so leave in that year cannot be worked out."
            )
        for row in rows:
            holidays.add(row.date)
            if row.is_exchangeable:
                exchangeable.add(row.date)
    return frozenset(holidays), frozenset(exchangeable)


def ledger_entry_for(
    request: LeaveRequestEntity, *, created_by: int | None
) -> LeaveLedgerEntity | None:
    """The row approving a request writes, or None for sick leave.

    One row per request, dated where the leave starts and pointing back at
    it: per-day rows would multiply the ledger and buy nothing, since the
    request already says which days. Sick leave has no allowance and deducts
    nothing, so it produces no row at all -- not even a zero one, which would
    only be a row readers have to learn to ignore.

    Args:
        request: The request being approved.
        created_by: Who approved it.

    Returns:
        The row to write, or None.
    """
    if request.type is LeaveRequestType.SICK:
        return None

    entry_type = (
        LeaveEntryType.EXCHANGE_CREDIT
        if request.type is LeaveRequestType.EXCHANGE
        else LeaveEntryType.LEAVE_DEDUCTION
    )
    return LeaveLedgerEntity(
        user_id=request.user_id,
        entry_type=entry_type,
        hours=_balance_delta(request.type, request.hours),
        effective_date=request.start_date,
        source_request_id=request.leave_request_id,
        created_by=created_by,
    )


async def overdraft_now(
    session: AsyncSession,
    leave_ledger_repository,
    leave_request_repository,
    request: LeaveRequestEntity,
) -> bool:
    """Whether a waiting paid request is an overdraft against the balance as
    it stands now.

    The mark filed with a request goes stale: an admin adjustment, the weekly
    grant, or another request withdrawn or turned down all move what is left.
    This is the same test as at filing -- the balance less every paid hour
    still waiting, this request's included, must not go below zero -- run
    again for an approver who is looking at it today.

    Args:
        session: Active async session.
        leave_ledger_repository (LeaveLedgerRepository): The balance.
        leave_request_repository (LeaveRequestRepository): The hours held by
            waiting requests.
        request: A request still waiting.

    Returns:
        True when the balance does not cover it. Always False for sick leave
        and exchanges, which spend nothing.
    """
    if request.type is not LeaveRequestType.PAID:
        return False
    balance = await leave_ledger_repository.balance(session, request.user_id)
    held = await leave_request_repository.sum_pending_paid_hours(
        session, request.user_id
    )
    return balance - held < NO_HOURS


class LeaveRequestService:
    """The request lifecycle."""

    def __init__(
        self,
        logger,
        leave_request_repository,
        leave_ledger_repository,
        leave_holiday_repository,
        user_emails_repository,
        users_repository,
        redis_client,
        retry_utils,
        participant_resolver,
        approval_service,
    ):
        """
        Args:
            logger: Structured logger.
            leave_request_repository (LeaveRequestRepository): Requests.
            leave_ledger_repository (LeaveLedgerRepository): Ledger rows.
            leave_holiday_repository (LeaveHolidayRepository): The calendar.
            user_emails_repository (UserEmailsRepository): Finds the requester's
                corporate address, which is how their Azure profile is keyed.
            users_repository (UsersRepository): Names for an approver's queue.
            redis_client: Holds the cached employment profiles.
            retry_utils: Transient-failure retry wrapper.
            participant_resolver (LeaveParticipantResolver): Turns the manager's
                ldap into the account that will approve.
            approval_service (ApprovalService): Runs deciding and withdrawing,
                through the ``leave_approval`` handler.
        """
        self.logger = logger
        self.leave_request_repository = leave_request_repository
        self.leave_ledger_repository = leave_ledger_repository
        self.leave_holiday_repository = leave_holiday_repository
        self.user_emails_repository = user_emails_repository
        self.users_repository = users_repository
        self.redis_client = redis_client
        self.retry_utils = retry_utils
        self.participant_resolver = participant_resolver
        self.approval_service = approval_service

    async def submit(
        self,
        session: AsyncSession,
        user_id: int,
        request_type: LeaveRequestType,
        start_date: datetime.date,
        end_date: datetime.date,
        start_time: datetime.time | None,
        end_time: datetime.time | None,
        reason: str | None,
    ) -> LeaveRequestDto:
        """Files one request, or refuses it with a reason.

        Args:
            session: Active async session, committed once at the end.
            user_id: Who is asking.
            request_type: Paid, sick or exchange.
            start_date: First day.
            end_date: Last day, equal to the first for a single day.
            start_time: Only for a single day of leave.
            end_time: As above.
            reason: Free text, optional.

        Returns:
            The stored request. Sick leave of three days or less comes back
            already approved, with no approval behind it: nobody decided it,
            so ``decided_by`` is empty.

        Raises:
            ValueError: Any of the refusals. Each message says what to do
                about it, since every one of them is something a person has to
                fix rather than retry.
        """
        today = business_today()
        if start_date < today:
            raise ValueError(
                f"Leave cannot start on {start_date}, which has passed. The "
                "ledger is a history, so it is never written backwards."
            )
        if end_date < start_date:
            raise ValueError(f"{end_date} is before {start_date}.")

        approver_user_id = await self._approver_for(session, user_id)
        holidays, exchangeable = await load_calendar(
            session, self.leave_holiday_repository, today, start_date, end_date
        )

        hours = request_hours(
            request_type, start_date, end_date, start_time, end_time, holidays
        )
        if hours <= NO_HOURS:
            raise ValueError(
                "Those days are already time off, so there is nothing to request."
            )

        clashes = await self.leave_request_repository.list_overlapping(
            session, user_id, start_date, end_date
        )
        if clashes:
            named = ", ".join(
                f"#{clash.leave_request_id} ({clash.start_date} to {clash.end_date})"
                for clash in clashes
            )
            raise ValueError(f"These days are already covered by {named}.")

        if request_type is LeaveRequestType.EXCHANGE:
            self._check_exchangeable(start_date, end_date, exchangeable)

        notice_given = workdays_before(today, start_date, holidays)
        notice_needed = required_notice_workdays(hours)
        is_late_notice = self._notice(request_type, notice_given, notice_needed)

        request = LeaveRequestEntity(
            user_id=user_id,
            type=request_type,
            start_date=start_date,
            end_date=end_date,
            start_time=start_time,
            end_time=end_time,
            hours=hours,
            status=LeaveRequestStatus.PENDING,
            approver_user_id=approver_user_id,
            reason=reason,
            is_overdraft=await self._is_overdraft(
                session, user_id, request_type, hours
            ),
            is_late_notice=is_late_notice,
        )

        auto_approved = (
            request_type is LeaveRequestType.SICK and hours <= SICK_AUTO_APPROVE_HOURS
        )
        if auto_approved:
            # Approved on submission, and the approver is still recorded: what
            # is automatic is the decision, not who it belonged to. It never
            # goes to the approver, so there is no approval behind it, and
            # nobody is named as having decided it.
            request.status = LeaveRequestStatus.APPROVED

        stored = await self.leave_request_repository.add(session, request)
        approval = None
        if auto_approved:
            await session.commit()
        else:
            # Commits the request with its approval.
            approval = await self.approval_service.raise_request(
                session,
                action=LEAVE_APPROVAL,
                raised_by=user_id,
                target_id=str(stored.leave_request_id),
                payload=None,
                reason=None,
                reviewer_id=None,
            )
        self.logger.info(
            "Leave request %s: user %s, %s, %s to %s, %s hours, %s.",
            stored.leave_request_id,
            user_id,
            request_type.value,
            start_date,
            end_date,
            hours,
            stored.status.value,
        )
        return self._read_model(stored, approval)

    async def decide(
        self,
        session: AsyncSession,
        request_id: int,
        approver_user_id: int,
        approve: bool,
        comment: str | None = None,
    ) -> LeaveRequestDto:
        """Approves or rejects a pending request. Committed by the approval
        flow; approving writes the ledger row (see leave_request_handler).

        Args:
            session: Active async session.
            request_id: Which request.
            approver_user_id: Who is deciding. Must be the approver the request
                was submitted against.
            approve: True to approve, False to reject.
            comment: Why. Required to reject.

        Returns:
            The decided request.

        Raises:
            ValueError: No such request, or a rejection with no reason.
            PermissionError: Somebody other than the named approver. The
                approver was snapshotted at submission, so anybody else
                deciding would attribute the approval to the wrong person.
            ConflictError: It has already been decided, or approving it no
                longer holds (it has started, its hours have changed, or its
                owner is no longer active); it stays pending.
        """
        pending = await self._pending_approval(
            session,
            request_id,
            may_act=lambda leave: leave.approver_user_id == approver_user_id,
            refusal=f"Request {request_id} is for somebody else to decide.",
        )
        approval = await self.approval_service.decide(
            session,
            request_id=pending.request_id,
            actor_id=approver_user_id,
            approve=approve,
            comment=comment,
        )
        request = await self.leave_request_repository.get_by_id(session, request_id)
        self.logger.info(
            "Leave request %s %s by %s.",
            request_id,
            request.status.value,
            approver_user_id,
        )
        return self._read_model(request, approval)

    async def withdraw(
        self, session: AsyncSession, request_id: int, user_id: int
    ) -> LeaveRequestDto:
        """Takes back a request nobody has decided yet. Committed by the
        approval flow, which tells the approver.

        No manager needed: nothing has reached the ledger. Once approved a
        request stays approved -- see the module docstring.

        Args:
            session: Active async session.
            request_id: Which request.
            user_id: Who is taking it back. Must be its owner.

        Returns:
            The withdrawn request.

        Raises:
            ValueError: No such request.
            PermissionError: Somebody other than its owner.
            ConflictError: It has already been decided.
        """
        pending = await self._pending_approval(
            session,
            request_id,
            may_act=lambda leave: leave.user_id == user_id,
            refusal=f"Request {request_id} belongs to somebody else.",
        )
        approval = await self.approval_service.withdraw(
            session, request_id=pending.request_id, actor_id=user_id
        )
        request = await self.leave_request_repository.get_by_id(session, request_id)
        self.logger.info("Leave request %s withdrawn by %s.", request_id, user_id)
        return self._read_model(request, approval)

    async def list_own(
        self, session: AsyncSession, user_id: int
    ) -> list[LeaveRequestDto]:
        """One person's own requests, newest first.

        Args:
            session: Active async session.
            user_id: Whose requests.

        Returns:
            Their requests. No name on them: it would be the reader's own.
        """
        requests = await self.leave_request_repository.list_for_user(session, user_id)
        approvals = await self._approvals_of(session, requests)
        return [
            self._read_model(request, approvals.get(str(request.leave_request_id)))
            for request in requests
        ]

    async def list_for_approver(
        self, session: AsyncSession, approver_user_id: int
    ) -> list[LeaveRequestDto]:
        """Everything ever filed against one approver, oldest first.

        Every status, not just the ones waiting. Nobody carries a manager flag
        -- being an approver is not a permission, and a manager who gets no
        leave themselves has no employment profile to read it off -- so this
        list is what says somebody approves for others at all: it is non-empty
        exactly when somebody has filed against them. Narrowing it to pending
        would take that away the moment a manager finished deciding, and would
        leave nowhere to look up what they had decided.

        Each carries the name of whoever asked: a queue of user ids is
        unusable. A name that cannot be resolved is left empty rather than
        allowed to take the whole queue down -- a deleted account should not
        stop a manager working.

        A waiting paid request's overdraft mark is worked out again against
        the balance as it stands now, since the one filed with it goes stale;
        a decided one keeps the mark it was decided on.

        Args:
            session: Active async session.
            approver_user_id: The approver.

        Returns:
            The requests, decided ones included.
        """
        requests = await self.leave_request_repository.list_for_approver(
            session, approver_user_id, list(LeaveRequestStatus)
        )
        user_ids = sorted({request.user_id for request in requests})
        people = await self.users_repository.get_all_by_ids(session, user_ids)
        name_by_id = {
            person.user_id: user_display_name(
                first_name=person.first_name,
                last_name=person.last_name,
                preferred_name=person.preferred_name,
            )
            for person in people
        }
        addresses_by_id = await self.user_emails_repository.get_emails_by_user_ids(
            session, user_ids
        )
        ldap_by_id = {
            user_id: _ldap_from_addresses(addresses)
            for user_id, addresses in addresses_by_id.items()
        }
        # Only for what is still waiting: a decided request has already moved
        # the ledger, so there is no "would" left to answer.
        pending_user_ids = sorted({
            request.user_id
            for request in requests
            if request.status is LeaveRequestStatus.PENDING
        })
        balance_by_id = await self.leave_ledger_repository.balances_by_user_ids(
            session, pending_user_ids
        )
        held_by_id = {
            user_id: await self.leave_request_repository.sum_pending_paid_hours(
                session, user_id
            )
            for user_id in pending_user_ids
        }
        approvals = await self._approvals_of(session, requests)
        return [
            LeaveRequestDto.of(
                request,
                approval=approvals.get(str(request.leave_request_id)),
                employee_name=name_by_id.get(request.user_id),
                employee_ldap=ldap_by_id.get(request.user_id),
                required_notice_workdays=self._required_notice(request),
                is_overdraft=self._overdraft_mark(request, balance_by_id, held_by_id),
                **self._balance_pair(request, balance_by_id),
            )
            for request in requests
        ]

    async def standing(self, session: AsyncSession, user_id: int) -> "LeaveStanding":
        """Where this person stands: whether leave applies, and the three
        figures a dashboard answers "what can I spend" with.

        All three are computed here. Available is the balance less the hours
        already held by undecided requests, which is the same definition the
        overdraft mark uses -- so a card cannot say somebody can afford leave
        that filing would then flag. Used is this year only: a figure summed
        across years would say somebody spent this year what they spent over
        their whole employment.

        The figures are None for somebody the feature does not apply to. Zero
        would read as an entitlement of nothing rather than as a feature with
        nothing to do with them.

        Args:
            session: Active async session.
            user_id: Whose standing.

        Returns:
            The standing.
        """
        if not await self.coverage(session, user_id):
            return LeaveStanding(
                is_covered=False, available=None, pending=None, used=None
            )

        balance = await self.leave_ledger_repository.balance(session, user_id)
        pending = await self.leave_request_repository.sum_pending_paid_hours(
            session, user_id
        )
        deducted = await self.leave_ledger_repository.sum_deductions_for_year(
            session, user_id, business_today().year
        )
        return LeaveStanding(
            is_covered=True,
            available=balance - pending,
            pending=pending,
            # Stored negative; shown as an amount spent.
            used=-deducted,
        )

    async def coverage(self, session: AsyncSession, user_id: int) -> bool:
        """Whether the leave system has anything to do with this account.

        Two ways of being covered, taken as an or. The nightly sync writes an
        employment profile for the people in scope -- full-time and based in
        China -- and deletes everybody else's, so being in that cache is the
        live answer. A ledger row is the second: rows are only ever written for
        people who were covered, so somebody who has since left the population
        keeps their history rather than having it vanish the night their
        profile is dropped.

        The second half is also the degradation path. Reading Redis alone means
        that while the cache is cold, or before the sync has ever run, *nobody*
        looks covered and the whole feature disappears for everyone. With the
        ledger in the or, what disappears is only somebody in scope who has
        never been granted an hour.

        The corporate address is the whole of the join onto Azure, so an account
        without one has no profile to look for and the cache is not consulted at
        all -- there is no key to ask about, and the answer can only come from
        the ledger.

        Args:
            session: Active async session.
            user_id: Whose standing.

        Returns:
            True when the feature applies to them.
        """
        rows = await self.user_emails_repository.list_by_user_id(session, user_id)
        ldap = _ldap_from_addresses(row.email for row in rows)
        if ldap is not None:
            profiles = self.retry_utils.get_retry_on_transient(
                self.redis_client.hgetall, LEAVE_EMPLOYMENT_KEY
            )
            if ldap in (profiles or {}):
                return True

        # Presence of rows, never the figure they sum to: a balance of zero is
        # a real balance, and testing the total would drop exactly the people
        # whose credits and deductions cancel out.
        balances = await self.leave_ledger_repository.balances_by_user_ids(
            session, [user_id]
        )
        return user_id in balances

    def _read_model(
        self, request: LeaveRequestEntity, approval=None
    ) -> LeaveRequestDto:
        """One request as it is read back, in the shape the lists use.

        One resource answers with one shape, and the read model is that shape.
        The stored row cannot be sent in its place: FastAPI's encoder falls
        through to ``vars()`` for an ORM object, which sends snake_case keys
        where every list endpoint sends camelCase and puts ``hours`` through
        the Decimal encoder into a float -- 78.46 as 78.45999999999999, the one
        thing LeaveRequestDto exists to prevent.

        No name or ldap: whoever filed, took back or decided this is looking at
        a request they are already party to. No balance pair either -- that is
        the "where would approving leave me" figure an approver reads while a
        request is still waiting, and it has no answer once the ledger has
        moved.
        """
        return LeaveRequestDto.of(
            request,
            approval=approval,
            required_notice_workdays=self._required_notice(request),
        )

    async def _approvals_of(self, session: AsyncSession, requests) -> dict:
        """The approval behind each of these requests, by request id as text.

        Sick leave approved on submission has none.
        """
        return await self.approval_service.latest_for_targets(
            session,
            LEAVE_APPROVAL,
            [str(request.leave_request_id) for request in requests],
        )

    @staticmethod
    def _overdraft_mark(
        request: LeaveRequestEntity,
        balance_by_id: dict[int, Decimal],
        held_by_id: dict[int, Decimal],
    ) -> bool:
        """The overdraft mark an approver reads: worked out now for a waiting
        paid request, the stored one otherwise. Same test as ``overdraft_now``.
        """
        if (
            request.status is not LeaveRequestStatus.PENDING
            or request.type is not LeaveRequestType.PAID
        ):
            return request.is_overdraft
        balance = balance_by_id.get(request.user_id, NO_HOURS)
        return balance - held_by_id.get(request.user_id, NO_HOURS) < NO_HOURS

    @staticmethod
    def _required_notice(request: LeaveRequestEntity) -> int | None:
        """Working days of notice the rule asked of this request.

        Stated on every view of a request, not only where it fell short, so
        two views of one request cannot disagree about what it owed. Sick leave
        owes none: nobody schedules illness.
        """
        if request.type is LeaveRequestType.SICK:
            return None
        return required_notice_workdays(request.hours)

    @staticmethod
    def _balance_pair(
        request: LeaveRequestEntity, balance_by_id: dict[int, Decimal]
    ) -> dict[str, Decimal | None]:
        """Where this person's balance stands, and where approving would put it.

        Both empty unless the request is still waiting. An empty ledger means a
        balance of zero rather than an unknown one: the person is covered -- they
        filed this -- they simply have no rows yet.

        Two requests from the same person are each measured against the same
        balance, since neither has reached the ledger. Deciding one reloads the
        list, so the next is measured against the balance it actually faces.
        """
        if request.status is not LeaveRequestStatus.PENDING:
            return {"balance_before": None, "balance_after": None}
        before = balance_by_id.get(request.user_id, NO_HOURS)
        return {
            "balance_before": before,
            "balance_after": before + _balance_delta(request.type, request.hours),
        }

    async def _pending_approval(
        self, session: AsyncSession, request_id: int, *, may_act, refusal: str
    ):
        """The approval a request is waiting on, for somebody who may act on it.

        Who is asking is judged before whether the request is still waiting,
        so that somebody with no part in a request cannot learn its status by
        trying to act on it.

        Args:
            session: Active async session.
            request_id: Which request.
            may_act: Whether the caller may act on this request.
            refusal: What to tell them when they may not.

        Raises:
            ValueError: No such request.
            PermissionError: The caller has no part in it.
            ConflictError: It is not waiting on anybody: decided, withdrawn,
                or sick leave approved on submission.
        """
        request = await self.leave_request_repository.get_by_id(session, request_id)
        if request is None:
            raise ValueError(f"No leave request {request_id}.")
        if not may_act(request):
            raise PermissionError(refusal)
        approval = await self.approval_service.get_pending_for_target(
            session, LEAVE_APPROVAL, str(request_id)
        )
        if approval is None:
            raise ConflictError(
                f"Request {request_id} is already {request.status.value}."
            )
        return approval

    def _notice(self, request_type: LeaveRequestType, given: int, needed: int) -> bool:
        """Whether to mark short notice, having refused it where it is hard.

        Sick leave is exempt: nobody schedules illness, and a mark nobody can
        act on is noise. An exchange is refused outright rather than marked --
        the office has to plan for somebody being in, and a flag on the request
        does not do that. Paid leave is marked and left to the manager.

        Raises:
            ValueError: An exchange with too little notice.
        """
        if request_type is LeaveRequestType.SICK:
            return False
        if given >= needed:
            return False
        if request_type is LeaveRequestType.EXCHANGE:
            raise ValueError(
                f"An exchange needs {needed} working days' notice and this has {given}."
            )
        return True

    def _check_exchangeable(
        self,
        start_date: datetime.date,
        end_date: datetime.date,
        exchangeable: frozenset[datetime.date],
    ) -> None:
        """Refuses the whole request if any day cannot be exchanged.

        Not "credit the days that qualify": somebody would come in on a day
        that bought nothing and only find out afterwards.

        Raises:
            ValueError: Naming the days, so the person can fix the range.
        """
        day = start_date
        ineligible = []
        while day <= end_date:
            if day not in exchangeable:
                ineligible.append(str(day))
            day += datetime.timedelta(days=1)
        if ineligible:
            raise ValueError(
                "These days are not exchangeable company holidays: "
                f"{', '.join(ineligible)}."
            )

    async def _is_overdraft(
        self,
        session: AsyncSession,
        user_id: int,
        request_type: LeaveRequestType,
        hours: Decimal,
    ) -> bool:
        """Whether the balance covers this request at the moment it is filed.

        A mark, never a refusal: an L1 has no annual entitlement at all, so
        refusing on the balance would leave them unable to take a single paid
        day. Hours already waiting on a decision count against it, or two
        pending requests could both be paid out of the same hours.

        Sick leave never touches the balance, so it is never an overdraft.
        """
        if request_type is not LeaveRequestType.PAID:
            return False

        balance = await self.leave_ledger_repository.balance(session, user_id)
        held = await self.leave_request_repository.sum_pending_paid_hours(
            session, user_id
        )
        return balance - held < hours

    async def _approver_for(self, session: AsyncSession, user_id: int) -> int:
        """The account that will decide this person's requests.

        A snapshot taken now, not a lookup at decision time: changing manager
        later must not repoint a request somebody has already decided.

        Raises:
            ValueError: They have no corporate address, are not in the leave
                system, have no manager in Azure, or their manager has no
                purrf account. Each is a data fix rather than something to
                retry, and the message says which. Refusing beats approving
                automatically: a blank manager field would otherwise become
                leave nobody approved, and it could not be undone afterwards.
        """
        ldap = await self._ldap_of(session, user_id)
        profiles = self.retry_utils.get_retry_on_transient(
            self.redis_client.hgetall, LEAVE_EMPLOYMENT_KEY
        )
        raw = (profiles or {}).get(ldap)
        if raw is None:
            raise ValueError(
                "The leave system does not cover this account. It covers "
                "full-time employees based in China."
            )

        manager_ldap = json.loads(raw).get("manager_ldap")
        if not manager_ldap:
            raise ValueError(
                "Your Azure record has no manager, so there is nobody to "
                "approve this. Ask HR to fill it in -- this is missing data, "
                "not a fault in the system."
            )

        resolved = await self.participant_resolver.resolve(session, [manager_ldap])
        if manager_ldap not in resolved.by_ldap:
            raise ValueError(
                f"Your manager ({manager_ldap}) has no purrf account, so they "
                "cannot approve anything yet."
            )
        return resolved.by_ldap[manager_ldap]

    async def _ldap_of(self, session: AsyncSession, user_id: int) -> str:
        """This account's Azure ldap, taken from its corporate address."""
        rows = await self.user_emails_repository.list_by_user_id(session, user_id)
        ldap = _ldap_from_addresses(row.email for row in rows)
        if ldap is None:
            raise ValueError(
                "This account has no corporate address, so its Azure record "
                "cannot be found."
            )
        return ldap
