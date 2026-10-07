"""Renders the leave request events into (subject, HTML body).

What the request was for is read from the snapshot the event carries
(employeeName, leaveType, startDate, endDate, hours), so an email delivered
late still says what was true when it happened. The employee's reason and the
manager's comment are read from their rows, which never change them once
written.

Importing this module registers every renderer. ``fast_app_factory`` imports it
once at startup for that side effect.
"""

import html

from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.leave_enums import LeaveEvent
from backend.common.name_utils import user_display_name
from backend.entity.event_entity import EventEntity
from backend.leave import notification_email_copy as copy
from backend.notification_management.render_registry import register_render
from backend.repository.approval_request_repository import (
    ApprovalRequestRepository,
)
from backend.repository.leave_request_repository import LeaveRequestRepository
from backend.repository.users_repository import UsersRepository

# Stateless, so these module-level instances serve every render.
_users_repository = UsersRepository()
_approval_request_repository = ApprovalRequestRepository()
_leave_request_repository = LeaveRequestRepository()


async def _actor(session: AsyncSession, event: EventEntity, fallback: str) -> str:
    """Who acted, HTML-escaped, or the fallback when nobody can be named."""
    if event.actor_id is not None:
        person = await _users_repository.get_user_by_user_id(session, event.actor_id)
        if person is not None:
            name = user_display_name(
                first_name=person.first_name,
                last_name=person.last_name,
                preferred_name=person.preferred_name,
            )
            if name:
                return html.escape(name)
    return html.escape(fallback)


def _employee(event: EventEntity) -> str:
    return html.escape(event.details.get("employeeName") or "Somebody")


@register_render(LeaveEvent.REQUEST_SUBMITTED)
async def _render_submitted(session: AsyncSession, event: EventEntity):
    """Tell the manager a request is waiting on them."""
    details = event.details
    leave = await _leave_request_repository.get_by_id(session, event.subject_id)
    return copy.request_submitted(
        _employee(event),
        details.get("leaveType"),
        details.get("startDate"),
        details.get("endDate"),
        details.get("hours"),
        leave.reason if leave is not None else None,
    )


@register_render(LeaveEvent.REQUEST_DECIDED)
async def _render_decided(session: AsyncSession, event: EventEntity):
    """Tell the employee how their manager decided, or the manager that the
    request was withdrawn."""
    details = event.details
    if details.get("decision") == "withdrawn":
        return copy.request_withdrawn(
            _employee(event),
            details.get("leaveType"),
            details.get("startDate"),
            details.get("endDate"),
        )
    row = await _approval_request_repository.get(session, int(details["requestId"]))
    return copy.request_decided(
        await _actor(session, event, "Your manager"),
        details.get("decision", ""),
        details.get("leaveType"),
        details.get("startDate"),
        details.get("endDate"),
        row.decision_comment if row is not None else None,
    )
