"""A leave request, as an approval.

The employee's manager decides it: the manager was looked up when the
request was filed and stored on it, and that is who reviews it. Nobody
chooses or changes the reviewer. The request's own status says where it is
-- the overlap check, balances and the calendar read it -- so this handler
moves it: approving writes the ledger row, rejecting and withdrawing close
it.

Approving re-checks three things that can stop being true while a request
waits, and refuses rather than writes a ledger row that is wrong: the leave
has already started, a holiday entered since has changed its hours, or the
employee is no longer active.
"""

from backend.approval.approval_handler import ApprovalHandler
from backend.common.approval_enums import ApprovalRequestStatus
from backend.common.leave_enums import (
    LEAVE_APPROVAL,
    LEAVE_REQUEST_SUBJECT,
    LeaveEvent,
    LeaveRequestStatus,
)
from backend.common.name_utils import user_display_name
from backend.leave.leave_clock import business_today
from backend.leave.leave_request_service import (
    ledger_entry_for,
    load_calendar,
    overdraft_now,
)
from backend.leave.leave_workdays import request_hours


class LeaveRequestHandler(ApprovalHandler):
    action = LEAVE_APPROVAL
    target_type = LEAVE_REQUEST_SUBJECT
    subject_type = LEAVE_REQUEST_SUBJECT
    raised_event = LeaveEvent.REQUEST_SUBMITTED
    reassigned_event = LeaveEvent.REQUEST_REASSIGNED
    decided_event = LeaveEvent.REQUEST_DECIDED
    review_permission = None
    raiser_may_reassign = False

    def __init__(
        self,
        leave_request_repository,
        leave_ledger_repository,
        leave_holiday_repository,
        users_repository,
    ):
        """
        Args:
            leave_request_repository (LeaveRequestRepository): The requests.
            leave_ledger_repository (LeaveLedgerRepository): Where an approval
                writes, and the balance the overdraft is judged against.
            leave_holiday_repository (LeaveHolidayRepository): The calendar the
                hours are re-counted against.
            users_repository (UsersRepository): Whether the employee is still
                active, and their name for the events.
        """
        self._requests = leave_request_repository
        self._ledger = leave_ledger_repository
        self._holidays = leave_holiday_repository
        self._users = users_repository

    def subject_id(self, request) -> int:
        return int(request.target_id)

    async def event_details(self, session, request) -> dict:
        leave = await self._leave(session, request)
        employee = await self._users.get_user_by_user_id(session, leave.user_id)
        return {
            "employeeName": (
                user_display_name(
                    first_name=employee.first_name,
                    last_name=employee.last_name,
                    preferred_name=employee.preferred_name,
                )
                if employee is not None
                else ""
            ),
            "leaveType": leave.type.value,
            "startDate": leave.start_date.isoformat(),
            "endDate": leave.end_date.isoformat(),
            "hours": f"{leave.hours:.2f}",
        }

    async def assign_reviewer(
        self, session, *, raised_by: int, target_id: str, payload: dict
    ) -> int:
        # The manager looked up when the request was filed.
        return (await self._leave_by_id(session, int(target_id))).approver_user_id

    async def check_raise(
        self, session, *, raised_by: int, target_id: str, payload: dict
    ) -> None:
        leave = await self._leave_by_id(session, int(target_id))
        if leave.user_id != raised_by:
            raise PermissionError(f"Request {target_id} belongs to somebody else.")
        if leave.status is not LeaveRequestStatus.PENDING:
            raise ValueError(f"Request {target_id} is already {leave.status.value}.")

    async def problems_at_approval(self, session, request) -> list[str]:
        leave = await self._leave(session, request, for_update=True)
        today = business_today()
        problems = []
        if leave.start_date < today:
            # The same rule submission enforces: the ledger is a history and
            # is never written backwards.
            problems.append(
                f"This leave started on {leave.start_date}, so it can no longer "
                "be approved. Reject it and ask for it to be filed again."
            )
        else:
            try:
                holidays, _ = await load_calendar(
                    session, self._holidays, today, leave.start_date, leave.end_date
                )
            except ValueError as exc:
                problems.append(str(exc))
            else:
                hours = request_hours(
                    leave.type,
                    leave.start_date,
                    leave.end_date,
                    leave.start_time,
                    leave.end_time,
                    holidays,
                )
                if hours != leave.hours:
                    problems.append(
                        f"This request is for {leave.hours:.2f} hours, but with "
                        f"the company holidays entered since it comes to "
                        f"{hours:.2f}. Reject it and ask for it to be filed again."
                    )
        employee = await self._users.get_user_by_user_id(session, leave.user_id)
        if employee is None or not employee.is_active:
            problems.append(
                "This person's account is no longer active, so their leave "
                "cannot be approved."
            )
        return problems

    async def execute(self, session, request, *, actor_id: int) -> None:
        leave = await self._leave(session, request, for_update=True)
        # The mark the approver is shown is worked out against the balance as
        # it stands now, and the one in force when they approved is kept.
        leave.is_overdraft = await overdraft_now(
            session, self._ledger, self._requests, leave
        )
        leave.status = LeaveRequestStatus.APPROVED
        entry = ledger_entry_for(leave, created_by=actor_id)
        if entry is not None:
            await self._ledger.add_entries(session, [entry])

    async def revert(self, session, request, outcome) -> None:
        leave = await self._leave(session, request, for_update=True)
        leave.status = (
            LeaveRequestStatus.WITHDRAWN
            if outcome is ApprovalRequestStatus.WITHDRAWN
            else LeaveRequestStatus.REJECTED
        )

    async def _leave(self, session, request, *, for_update: bool = False):
        return await self._leave_by_id(
            session, int(request.target_id), for_update=for_update
        )

    async def _leave_by_id(self, session, leave_request_id: int, *, for_update=False):
        leave = await self._requests.get_by_id(
            session, leave_request_id, for_update=for_update
        )
        if leave is None:
            raise ValueError(f"No leave request {leave_request_id}.")
        return leave
