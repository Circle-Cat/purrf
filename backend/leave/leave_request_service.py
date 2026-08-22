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
"""

import datetime
import json
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.constants import INTERNAL_GOOGLE_ACCOUNT_DOMAIN
from backend.common.leave_enums import (
    LeaveEntryType,
    LeaveRequestStatus,
    LeaveRequestType,
)
from backend.common.name_utils import partner_display_name
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
    ) -> LeaveRequestEntity:
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
            already approved, with ``decided_by`` empty: nobody decided it.

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
        holidays, exchangeable = await self._calendar(
            session, today, start_date, end_date
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

        if request_type is LeaveRequestType.SICK and hours <= SICK_AUTO_APPROVE_HOURS:
            # Approved on submission, and the approver is still recorded: what
            # is automatic is the decision, not who it belonged to. decided_by
            # stays empty, which is what says no person made it -- and it is
            # the same convention the ledger uses for a row a job wrote.
            request.status = LeaveRequestStatus.APPROVED
            request.decided_at = datetime.datetime.now(datetime.timezone.utc)

        stored = await self.leave_request_repository.add(session, request)
        await session.commit()
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
        return stored

    async def decide(
        self,
        session: AsyncSession,
        request_id: int,
        approver_user_id: int,
        approve: bool,
    ) -> LeaveRequestEntity:
        """Approves or rejects a pending request, writing the ledger row.

        Approving is the only thing that moves hours. One row per request,
        dated where the leave starts and pointing back at it: per-day rows
        would multiply the ledger and buy nothing, since the request already
        says which days.

        Args:
            session: Active async session, committed once at the end.
            request_id: Which request.
            approver_user_id: Who is deciding. Must be the approver the request
                was submitted against.
            approve: True to approve, False to reject.

        Returns:
            The decided request.

        Raises:
            ValueError: No such request, or it has already been decided --
                deciding twice would write a second deduction.
            PermissionError: Somebody other than the named approver. The
                approver was snapshotted at submission, so anybody else
                deciding would attribute the approval to the wrong person.
        """
        request = await self._pending_request(session, request_id)
        if request.approver_user_id != approver_user_id:
            raise PermissionError(
                f"Request {request_id} is for somebody else to decide."
            )

        request.status = (
            LeaveRequestStatus.APPROVED if approve else LeaveRequestStatus.REJECTED
        )
        request.decided_by = approver_user_id
        request.decided_at = datetime.datetime.now(datetime.timezone.utc)

        if approve:
            entry = self._ledger_entry(request, approver_user_id)
            if entry is not None:
                await self.leave_ledger_repository.add_entries(session, [entry])
        await session.commit()
        self.logger.info(
            "Leave request %s %s by %s.",
            request_id,
            request.status.value,
            approver_user_id,
        )
        return request

    async def withdraw(
        self, session: AsyncSession, request_id: int, user_id: int
    ) -> LeaveRequestEntity:
        """Takes back a request nobody has decided yet.

        No manager needed: nothing has reached the ledger. Once approved a
        request stays approved -- see the module docstring.

        Args:
            session: Active async session, committed once at the end.
            request_id: Which request.
            user_id: Who is taking it back. Must be its owner.

        Returns:
            The withdrawn request.

        Raises:
            ValueError: No such request, or it has already been decided.
            PermissionError: Somebody other than its owner.
        """
        request = await self._pending_request(session, request_id)
        if request.user_id != user_id:
            raise PermissionError(f"Request {request_id} belongs to somebody else.")

        request.status = LeaveRequestStatus.WITHDRAWN
        await session.commit()
        self.logger.info("Leave request %s withdrawn by %s.", request_id, user_id)
        return request

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
        return [
            LeaveRequestDto.of(
                request, required_notice_workdays=self._required_notice(request)
            )
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
            person.user_id: partner_display_name(
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
        return [
            LeaveRequestDto.of(
                request,
                employee_name=name_by_id.get(request.user_id),
                employee_ldap=ldap_by_id.get(request.user_id),
                required_notice_workdays=self._required_notice(request),
                **self._balance_pair(request, balance_by_id),
            )
            for request in requests
        ]

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

    async def _pending_request(
        self, session: AsyncSession, request_id: int
    ) -> LeaveRequestEntity:
        """Loads a request that is still awaiting a decision."""
        request = await self.leave_request_repository.get_by_id(session, request_id)
        if request is None:
            raise ValueError(f"No leave request {request_id}.")
        if request.status is not LeaveRequestStatus.PENDING:
            raise ValueError(f"Request {request_id} is already {request.status.value}.")
        return request

    def _ledger_entry(
        self, request: LeaveRequestEntity, approver_user_id: int
    ) -> LeaveLedgerEntity | None:
        """The row an approval writes, or None for sick leave.

        Sick leave has no allowance and deducts nothing, so it produces no row
        at all -- not even a zero one, which would only be a row readers have
        to learn to ignore.
        """
        if request.type is LeaveRequestType.SICK:
            return None

        entry_type = (
            LeaveEntryType.EXCHANGE_CREDIT
            if request.type is LeaveRequestType.EXCHANGE
            else LeaveEntryType.LEAVE_DEDUCTION
        )
        hours = _balance_delta(request.type, request.hours)

        return LeaveLedgerEntity(
            user_id=request.user_id,
            entry_type=entry_type,
            hours=hours,
            effective_date=request.start_date,
            source_request_id=request.leave_request_id,
            created_by=approver_user_id,
        )

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

    async def _calendar(
        self,
        session: AsyncSession,
        today: datetime.date,
        start_date: datetime.date,
        end_date: datetime.date,
    ) -> tuple[frozenset[datetime.date], frozenset[datetime.date]]:
        """Company holidays covering the request and the notice window.

        Every year the request itself touches must be entered. Without it the
        hours would be computed against a year with no holidays in it and
        quietly come out too high.

        The notice window can reach back into an earlier year -- asking in
        December for leave in January -- and that year is not required to be
        entered. A missing calendar there makes the notice count generous
        rather than wrong, which is the harmless direction.

        Returns:
            All the holiday dates, and the subset that may be exchanged.

        Raises:
            ValueError: A year the request covers has no holidays entered.
        """
        holidays: set[datetime.date] = set()
        exchangeable: set[datetime.date] = set()
        for year in range(min(today.year, start_date.year), end_date.year + 1):
            rows = await self.leave_holiday_repository.list_by_year(session, year)
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
