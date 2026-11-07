"""Where each notification's reader goes to act on it.

A link is an app path such as ``/recruiting/applications/42``, never an
absolute URL, worked out from the event and the recipient: two people told
about one event can be sent to different pages. ``None`` means there is no
page to send them to.

Every event type the bell can receive is either in ``_RULES`` or in
``LINKLESS`` -- a shared-fixture test fails on a type in neither, so a new
event cannot reach the bell without someone deciding where it leads.

Paths mirror ``frontend/src/constants/RoutePaths.jsx`` and the query
parameters the destination pages already read; nothing here invents a new
one.

Lives beside the bell's service rather than in ``notification_management``
because it reads posting ownership through ``pipeline_owners``, and this
package already depends on that one.
"""

from typing import Awaitable, Callable, Iterable
from urllib.parse import urlencode

from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.inbox_enums import InboxEvent
from backend.common.leave_enums import LeaveEvent
from backend.common.mentorship_enums import MentorshipEvent
from backend.common.ops_enums import OpsEvent
from backend.common.permissions import Permission
from backend.common.recruiting_enums import RecruitingEvent
from backend.common.user_enums import UserEvent
from backend.communication.thread_service import service_from
from backend.entity.event_entity import EventEntity
from backend.recruiting.pipeline_owners import normalized_owner_ids
from backend.repository.application_assignment_repository import (
    ApplicationAssignmentRepository,
)
from backend.repository.approval_request_repository import (
    ApprovalRequestRepository,
)
from backend.repository.email_thread_repository import EmailThreadRepository
from backend.repository.job_repository import JobRepository
from backend.repository.leave_request_repository import LeaveRequestRepository
from backend.repository.mentorship_email_repository import MentorshipEmailRepository
from backend.repository.user_permissions_repository import UserPermissionsRepository
from backend.repository.users_repository import UsersRepository

# Stateless, so these module-level instances serve every lookup.
_assignments = ApplicationAssignmentRepository()
_approval_requests = ApprovalRequestRepository()
_threads = EmailThreadRepository()
_jobs = JobRepository()
_leave_requests = LeaveRequestRepository()
_mentorship_emails = MentorshipEmailRepository()
_permissions = UserPermissionsRepository()
_users = UsersRepository()

# The mentorship approval actions as the approval rows name them; the
# handlers own the constants, and a test holds these to them.
PUBLISH_MATCHING = "publish_matching"
END_PAIR = "end_pair"

# The block-request sources, as ``block_service.RAISE_PERMISSION_BY_SOURCE``
# names them; a test holds these to it.
MENTORSHIP_PARTICIPANT_SOURCE = "mentorship_participant"
RECRUITING_APPLICATION_SOURCE = "recruiting_application"

# Event types that reach the bell but have no page to act on.
LINKLESS = frozenset({OpsEvent.GMAIL_SYNC_ALERT})

# Application events that can reach a current assignee. An assignee who
# neither owns the posting nor reads every application sees the application
# page only in evaluate mode; without it the right column is empty.
_ASSIGNEE_AUDIENCE = frozenset({
    RecruitingEvent.STAGE_CHANGED,
    RecruitingEvent.ROUND_ADVANCED,
    RecruitingEvent.REASSIGNED,
    RecruitingEvent.INTERVIEW_SCHEDULED,
    RecruitingEvent.INTERVIEW_UPDATED,
    RecruitingEvent.INTERVIEW_CANCELLED,
    RecruitingEvent.AUTO_ASSIGNED,
    RecruitingEvent.MENTIONED,
})

_UNSET = object()


def _path(base: str, **params) -> str:
    """``base`` with the given query parameters, the None ones left out."""
    query = urlencode({k: v for k, v in params.items() if v is not None})
    return f"{base}?{query}" if query else base


def _application_page(application_id) -> str:
    return f"/recruiting/applications/{application_id}"


def _participant(user_id, round_id=None, review=None) -> str:
    """A person's mentorship page, as ``participantLink`` builds it."""
    return _path(
        f"/mentorship-management/participants/{user_id}", round=round_id, review=review
    )


def _matching(round_id) -> str:
    return f"/mentorship-management/matching/{round_id}"


class NotificationLinks:
    """Works out links for one recipient, reusing what it has read.

    One instance serves one page of the bell, or one email: the recipient's
    permissions are read at most once, and each approval request, posting and
    assignment set at most once however many rows name it.
    """

    def __init__(
        self,
        session: AsyncSession,
        user_id: int,
        *,
        jobs_by_application: dict | None = None,
    ):
        """
        Args:
            session (AsyncSession): Active database async session.
            user_id (int): The recipient.
            jobs_by_application (dict[int, JobEntity | None] | None): Postings
                already loaded, by application id, so ownership costs no
                query for them.
        """
        self.session = session
        self.user_id = user_id
        self._jobs_by_application = dict(jobs_by_application or {})
        self._approval_requests: dict[int, object] = {}
        self._assignees: dict[int, set[int]] = {}
        self._reads_all = _UNSET

    async def prefetch(self, events: Iterable[EventEntity]) -> None:
        """Read in one query every approval request these events name.

        Args:
            events (Iterable[EventEntity]): The events about to be linked.
        """
        ids = {
            int(e.details["requestId"])
            for e in events
            if (e.details or {}).get("requestId") is not None
        } - set(self._approval_requests)
        for row in await _approval_requests.get_by_ids(self.session, sorted(ids)):
            self._approval_requests[row.request_id] = row
        for request_id in ids:
            self._approval_requests.setdefault(request_id, None)

    async def of(self, event: EventEntity) -> str | None:
        """Where the recipient acts on ``event``.

        Args:
            event (EventEntity): The event the notification is about.

        Returns:
            str | None: An app path, or None when there is no page for it,
                including for a type with no rule: a shared-fixture test
                keeps every type the bell can receive covered, so that is an
                old row whose event no longer notifies anyone.
        """
        rule = _RULES.get(event.event_type)
        return None if rule is None else await rule(self, event)

    async def _approval_request(self, event: EventEntity):
        raw = (event.details or {}).get("requestId")
        if raw is None:
            return None
        request_id = int(raw)
        if request_id not in self._approval_requests:
            self._approval_requests[request_id] = await _approval_requests.get(
                self.session, request_id
            )
        return self._approval_requests[request_id]

    async def _job_of_application(self, application_id: int):
        if application_id not in self._jobs_by_application:
            self._jobs_by_application[
                application_id
            ] = await _jobs.get_by_application_id(self.session, application_id)
        return self._jobs_by_application[application_id]

    async def _is_current_assignee(self, application_id: int) -> bool:
        if application_id not in self._assignees:
            self._assignees[
                application_id
            ] = await _assignments.get_current_assignee_ids(
                self.session, application_id
            )
        return self.user_id in self._assignees[application_id]

    async def _reads_every_application(self) -> bool:
        """Whether the recipient holds read.all, as the auth middleware
        resolves it: a super admin holds every permission without a grant."""
        if self._reads_all is _UNSET:
            user = await _users.get_user_by_user_id(self.session, self.user_id)
            if user is None:
                self._reads_all = False
            elif user.is_super_admin:
                self._reads_all = True
            else:
                names = await _permissions.get_active_permission_names(
                    self.session, self.user_id
                )
                self._reads_all = (
                    Permission.RECRUITING_APPLICATION_READ_ALL.value in names
                )
        return self._reads_all

    async def _application(self, event: EventEntity) -> str:
        """The application's page; in evaluate mode for a recipient who is
        there only as its current assignee."""
        application_id = event.subject_id
        path = _application_page(application_id)
        if event.event_type not in _ASSIGNEE_AUDIENCE:
            return path
        job = await self._job_of_application(application_id)
        owners = normalized_owner_ids(job.pipeline_config) if job is not None else []
        if self.user_id in owners:
            return path
        if not await self._is_current_assignee(application_id):
            return path
        if await self._reads_every_application():
            return path
        return _path(path, mode="evaluate")

    async def _posting(self, event: EventEntity) -> str:
        return f"/recruiting/postings/{event.subject_id}"

    async def _inbox_needs_reply(self, event: EventEntity) -> str:
        return _path("/inbox", service=(event.details or {}).get("service"))

    async def _inbox_bounced(self, event: EventEntity) -> str:
        thread = await _threads.get(self.session, event.subject_id)
        service = service_from(thread.context_type, None) if thread else None
        return _path("/inbox", service=str(service) if service else None)

    async def _leave_submitted(self, event: EventEntity) -> str:
        return "/leave/approvals"

    async def _leave_decided(self, event: EventEntity) -> str:
        """The employee reads the outcome on their requests; the manager is
        told only of a withdrawal, which leaves their approvals list."""
        leave = await _leave_requests.get_by_id(self.session, event.subject_id)
        if leave is not None and leave.user_id == self.user_id:
            return "/leave/requests"
        return "/leave/approvals"

    async def _mentorship_approval(
        self, event: EventEntity, review: bool
    ) -> str | None:
        """Where a mentorship request is decided, as ``approvalReviewLink``
        has it: a publish on the round's matching page, anything else on the
        page of the person it is about -- the mentee, for ending a pair --
        opened on the request while it still waits.
        """
        round_id = event.subject_id
        row = await self._approval_request(event)
        action = row.action if row is not None else (event.details or {}).get("action")
        if action == PUBLISH_MATCHING:
            return _matching(round_id)
        if row is None:
            return None
        payload = row.payload or {}
        person = (
            payload.get("mentee_id") if action == END_PAIR else payload.get("user_id")
        )
        if person is None:
            return None
        return _participant(person, round_id, row.request_id if review else None)

    async def _approval_waiting(self, event: EventEntity) -> str | None:
        return await self._mentorship_approval(event, review=True)

    async def _approval_decided(self, event: EventEntity) -> str | None:
        return await self._mentorship_approval(event, review=False)

    async def _participant_email(self, event: EventEntity) -> str | None:
        details = event.details or {}
        if details.get("userId") is None:
            return None
        return _participant(details["userId"], details.get("roundId"))

    async def _email_send(self, event: EventEntity) -> str:
        send = await _mentorship_emails.get_send(self.session, event.subject_id)
        return _path("/mentorship-management", round=send.round_id if send else None)

    async def _matching_run(self, event: EventEntity) -> str:
        return _matching(event.subject_id)

    async def _own_dashboard(self, event: EventEntity) -> str:
        return "/dashboard/me"

    async def _account(self, event: EventEntity) -> str:
        return _path("/admin/accounts", user_id=event.subject_id)

    async def _block_decided(self, event: EventEntity) -> str | None:
        """The reviewer back to the account; the raiser to the page they
        raised it from. A recruiting raiser may have no standing on the
        account console, so a request that does not name its application
        leads them nowhere."""
        row = await self._approval_request(event)
        if row is None:
            return None
        if row.reviewer_id == self.user_id:
            return await self._account(event)
        payload = row.payload or {}
        source = payload.get("raised_from")
        if source == MENTORSHIP_PARTICIPANT_SOURCE:
            return _participant(event.subject_id)
        if source == RECRUITING_APPLICATION_SOURCE and payload.get("application_id"):
            return _application_page(payload["application_id"])
        return None


Rule = Callable[[NotificationLinks, EventEntity], Awaitable[str | None]]

_RULES: dict[str, Rule] = {
    RecruitingEvent.REVIEW_OPENED: NotificationLinks._posting,
    RecruitingEvent.REVIEW_REASSIGNED: NotificationLinks._posting,
    RecruitingEvent.REVIEW_DECIDED: NotificationLinks._posting,
    RecruitingEvent.APPLICATION_SUBMITTED: NotificationLinks._application,
    RecruitingEvent.AUTO_REJECTED: NotificationLinks._application,
    RecruitingEvent.BLACKLISTED: NotificationLinks._application,
    RecruitingEvent.SUB_STATUS_CHANGED: NotificationLinks._application,
    RecruitingEvent.EVALUATION_CONFIRMED: NotificationLinks._application,
    RecruitingEvent.STAGE_CHANGED: NotificationLinks._application,
    RecruitingEvent.ROUND_ADVANCED: NotificationLinks._application,
    RecruitingEvent.REASSIGNED: NotificationLinks._application,
    RecruitingEvent.INTERVIEW_SCHEDULED: NotificationLinks._application,
    RecruitingEvent.INTERVIEW_UPDATED: NotificationLinks._application,
    RecruitingEvent.INTERVIEW_CANCELLED: NotificationLinks._application,
    RecruitingEvent.AUTO_ASSIGNED: NotificationLinks._application,
    RecruitingEvent.MENTIONED: NotificationLinks._application,
    RecruitingEvent.EMAIL_RECEIVED: NotificationLinks._application,
    RecruitingEvent.EMAIL_BOUNCED: NotificationLinks._application,
    InboxEvent.NEEDS_REPLY: NotificationLinks._inbox_needs_reply,
    InboxEvent.BOUNCED: NotificationLinks._inbox_bounced,
    LeaveEvent.REQUEST_SUBMITTED: NotificationLinks._leave_submitted,
    LeaveEvent.REQUEST_DECIDED: NotificationLinks._leave_decided,
    MentorshipEvent.APPROVAL_REQUESTED: NotificationLinks._approval_waiting,
    MentorshipEvent.APPROVAL_REASSIGNED: NotificationLinks._approval_waiting,
    MentorshipEvent.APPROVAL_DECIDED: NotificationLinks._approval_decided,
    MentorshipEvent.EMAIL_RECEIVED: NotificationLinks._participant_email,
    MentorshipEvent.EMAIL_BOUNCED: NotificationLinks._participant_email,
    MentorshipEvent.EMAIL_SEND_PREPARED: NotificationLinks._email_send,
    MentorshipEvent.MATCHING_RUN_COMPLETED: NotificationLinks._matching_run,
    MentorshipEvent.MENTOR_ADMITTED: NotificationLinks._own_dashboard,
    UserEvent.BLOCK_REQUESTED: NotificationLinks._account,
    UserEvent.BLOCK_REQUEST_REASSIGNED: NotificationLinks._account,
    UserEvent.BLOCK_REQUEST_DECIDED: NotificationLinks._block_decided,
}

# Read by the shared-fixture test: the types that have a rule.
LINKED = frozenset(_RULES)


async def link_for(
    session: AsyncSession, event: EventEntity, user_id: int
) -> str | None:
    """Where ``user_id`` acts on ``event``.

    Args:
        session (AsyncSession): Active database async session.
        event (EventEntity): The event the notification is about.
        user_id (int): The recipient.

    Returns:
        str | None: An app path, or None when there is no page for it.
    """
    return await NotificationLinks(session, user_id).of(event)


async def links_for_page(
    session: AsyncSession,
    events: Iterable[EventEntity],
    user_id: int,
    *,
    jobs_by_application: dict | None = None,
) -> dict[int, str | None]:
    """Links for one recipient's page of events, reading shared rows once.

    Args:
        session (AsyncSession): Active database async session.
        events (Iterable[EventEntity]): The page's events.
        user_id (int): The recipient.
        jobs_by_application (dict[int, JobEntity | None] | None): Postings
            already loaded, by application id.

    Returns:
        dict[int, str | None]: Link by event id.
    """
    events = list(events)
    links = NotificationLinks(session, user_id, jobs_by_application=jobs_by_application)
    await links.prefetch(events)
    return {event.event_id: await links.of(event) for event in events}
