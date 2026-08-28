import datetime
from decimal import Decimal

from backend.common.leave_enums import LeaveRequestType
from backend.dto.base_dto import BaseDto


def _hours(value: Decimal | None) -> str | None:
    """Two decimals as text, or nothing.

    Never a number: the encoder turns a Decimal into a float and 78.46 comes
    back as 78.45999999999999. A balance is a money-shaped figure and must not
    be touched by floating point on the way out.
    """
    return None if value is None else f"{Decimal(value):.2f}"


class LeaveRequestSubmitDto(BaseDto):
    """One request as it is filed.

    ``start_time`` and ``end_time`` only mean anything for a single day of
    leave: a range is always whole days, and an exchange is always whole days.
    Sending them anywhere else is refused rather than ignored.
    """

    type: LeaveRequestType
    start_date: datetime.date
    end_date: datetime.date
    start_time: datetime.time | None = None
    end_time: datetime.time | None = None
    reason: str | None = None


class LeaveDecisionDto(BaseDto):
    """A manager's answer to one request."""

    approve: bool


class LeaveRequestDto(BaseDto):
    """A request as it is read back.

    Hours are strings fixed to two decimals rather than numbers: FastAPI's
    encoder turns a Decimal into a float, and 78.46 comes back as
    78.45999999999999.

    ``employee_name`` and ``employee_ldap`` are filled in only where somebody
    is looking at another person's request -- a manager's queue. They are None
    on your own list, where they would be your own. Either can be None on its
    own: a name comes from the account and an ldap from its corporate address,
    and one can be missing while the other is not.

    ``decided_by`` empty on an approved request means nobody decided it: that
    is sick leave of three days or less, approved on submission.

    ``required_notice_workdays`` is the notice the rule asked of this request,
    in working days. The late-notice flag says only that it fell short; the
    number is what a reader needs, and it is sent rather than derived on screen
    so the notice rule lives in one place. None for sick leave, which owes no
    notice at all.

    ``balance_before`` and ``balance_after`` are the pair an approver decides
    on: where this person's balance stands and where approving would leave it.
    They are filled in only while a request is still waiting. Once it has been
    decided the ledger has already moved, so "where would this land" has no
    answer, and a number there would be read as the balance today.
    """

    request_id: int
    user_id: int
    employee_name: str | None
    employee_ldap: str | None
    type: str
    status: str
    start_date: datetime.date
    end_date: datetime.date
    start_time: datetime.time | None
    end_time: datetime.time | None
    hours: str
    is_overdraft: bool
    is_late_notice: bool
    reason: str | None
    approver_user_id: int
    decided_by: int | None
    decided_at: datetime.datetime | None
    required_notice_workdays: int | None
    balance_before: str | None
    balance_after: str | None

    @classmethod
    def of(
        cls,
        request,
        employee_name: str | None = None,
        employee_ldap: str | None = None,
        required_notice_workdays: int | None = None,
        balance_before: Decimal | None = None,
        balance_after: Decimal | None = None,
    ) -> "LeaveRequestDto":
        """Builds one from a stored request.

        Args:
            request (LeaveRequestEntity): The stored row.
            employee_name: Whose request it is, when the reader is somebody
                else.
            employee_ldap: That person's Azure ldap, when known.
            required_notice_workdays: Working days of notice the rule asked
                of it, or None where none was owed.
            balance_before: Their balance now, for a request still waiting.
            balance_after: Where approving it would leave that balance.

        Returns:
            The read model.
        """
        return cls(
            request_id=request.leave_request_id,
            user_id=request.user_id,
            employee_name=employee_name,
            employee_ldap=employee_ldap,
            type=request.type.value,
            status=request.status.value,
            start_date=request.start_date,
            end_date=request.end_date,
            start_time=request.start_time,
            end_time=request.end_time,
            hours=f"{Decimal(request.hours):.2f}",
            is_overdraft=request.is_overdraft,
            is_late_notice=request.is_late_notice,
            reason=request.reason,
            approver_user_id=request.approver_user_id,
            decided_by=request.decided_by,
            decided_at=request.decided_at,
            required_notice_workdays=required_notice_workdays,
            balance_before=_hours(balance_before),
            balance_after=_hours(balance_after),
        )
