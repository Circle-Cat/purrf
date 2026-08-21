import datetime
from decimal import Decimal

from backend.common.leave_enums import LeaveRequestType
from backend.dto.base_dto import BaseDto


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

    ``employee_name`` is filled in only where somebody is looking at another
    person's request -- a manager's queue. It is None on your own list, where
    the name would be your own.

    ``decided_by`` empty on an approved request means nobody decided it: that
    is sick leave of three days or less, approved on submission.
    """

    request_id: int
    user_id: int
    employee_name: str | None
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

    @classmethod
    def of(cls, request, employee_name: str | None = None) -> "LeaveRequestDto":
        """Builds one from a stored request.

        Args:
            request (LeaveRequestEntity): The stored row.
            employee_name: Whose request it is, when the reader is somebody
                else.

        Returns:
            The read model.
        """
        return cls(
            request_id=request.leave_request_id,
            user_id=request.user_id,
            employee_name=employee_name,
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
        )
