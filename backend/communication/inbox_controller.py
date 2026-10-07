"""HTTP routes of the Inbox: one list over every service's mail threads."""

from urllib.parse import quote

from fastapi import APIRouter, Depends, Query, Response

from backend.common.api_endpoints import (
    INBOX_ATTACHMENT_ENDPOINT,
    INBOX_COUNT_ENDPOINT,
    INBOX_PEOPLE_ENDPOINT,
    INBOX_THREAD_ARCHIVE_ENDPOINT,
    INBOX_THREAD_ASSIGN_OPTIONS_ENDPOINT,
    INBOX_THREAD_ASSIGNMENT_ENDPOINT,
    INBOX_THREAD_ENDPOINT,
    INBOX_THREAD_MOVE_ENDPOINT,
    INBOX_THREAD_REPLY_ENDPOINT,
    INBOX_THREAD_UNARCHIVE_ENDPOINT,
    INBOX_THREADS_ENDPOINT,
)
from backend.common.communication_enums import InboxService
from backend.common.fast_api_response_wrapper import api_response
from backend.common.permissions import Permission
from backend.communication.inbox_access import INBOX_GATE, SERVICE_PERMISSION
from backend.dto.inbox_dto import (
    InboxAssignRequestDto,
    InboxMoveRequestDto,
    InboxQueryDto,
    InboxReplyRequestDto,
)
from backend.dto.user_context_dto import UserContextDto
from backend.utils.permission_decorators import authenticate

# Only the services whose threads can be assigned to a person search people.
PEOPLE_GATE: list[Permission] = [
    SERVICE_PERMISSION[s] for s in (InboxService.MENTORSHIP, InboxService.RECRUITING)
]

_UNSAFE_IN_NAME = frozenset('/\\"')


def _attachment_disposition(name: str) -> str:
    """A ``Content-Disposition`` that downloads ``name`` and cannot name a path.

    Path separators, quotes and control characters are dropped, as are
    leading dots and spaces. The quoted ``filename`` is an ASCII stand-in;
    ``filename*`` (RFC 5987) carries the real name.

    Args:
        name (str): The file name as the sender wrote it.

    Returns:
        str: The header value.
    """
    cleaned = "".join(
        c
        for c in name
        if c not in _UNSAFE_IN_NAME and ord(c) >= 32 and ord(c) != 127
    ).lstrip(". ")
    cleaned = cleaned or "attachment"
    ascii_name = "".join(c if c.isascii() else "_" for c in cleaned)
    return (
        f'attachment; filename="{ascii_name}"; '
        f"filename*=UTF-8''{quote(cleaned, safe='')}"
    )


class InboxController:
    """FastAPI routes for the Inbox.

    Every route needs one of the Inbox permissions; each call then checks the
    thread's own service in ``InboxThreadService``, so a thread of a service
    the viewer cannot see answers as if it did not exist.
    """

    def __init__(self, inbox_thread_service, database):
        """
        Args:
            inbox_thread_service (InboxThreadService): Reads and acts on threads.
            database: Async session provider.
        """
        self.inbox_thread_service = inbox_thread_service
        self.database = database
        self.router = APIRouter(tags=["inbox"])

        routes = [
            (INBOX_THREADS_ENDPOINT, "GET", self.list_threads, INBOX_GATE),
            (INBOX_COUNT_ENDPOINT, "GET", self.count_needs_reply, INBOX_GATE),
            (INBOX_THREAD_ENDPOINT, "GET", self.get_thread, INBOX_GATE),
            (INBOX_THREAD_REPLY_ENDPOINT, "POST", self.reply, INBOX_GATE),
            (INBOX_THREAD_ARCHIVE_ENDPOINT, "POST", self.archive, INBOX_GATE),
            (INBOX_THREAD_UNARCHIVE_ENDPOINT, "POST", self.unarchive, INBOX_GATE),
            (INBOX_THREAD_ASSIGNMENT_ENDPOINT, "PUT", self.assign, INBOX_GATE),
            (INBOX_THREAD_ASSIGNMENT_ENDPOINT, "DELETE", self.unassign, INBOX_GATE),
            (INBOX_THREAD_MOVE_ENDPOINT, "POST", self.move, INBOX_GATE),
            (
                INBOX_THREAD_ASSIGN_OPTIONS_ENDPOINT,
                "GET",
                self.assign_options,
                INBOX_GATE,
            ),
            (INBOX_PEOPLE_ENDPOINT, "GET", self.search_people, PEOPLE_GATE),
            (
                INBOX_ATTACHMENT_ENDPOINT,
                "GET",
                self.download_attachment,
                INBOX_GATE,
            ),
        ]
        for path, method, handler, gate in routes:
            self.router.add_api_route(
                path,
                endpoint=authenticate(permissions=gate)(handler),
                methods=[method],
                response_model=None,
            )

    async def list_threads(
        self, current_user: UserContextDto, query: InboxQueryDto = Depends()
    ):
        """The visible threads, filtered, with Needs reply counts."""
        async with self.database.session() as session:
            result = await self.inbox_thread_service.list_threads(
                session, current_user, query
            )
        return api_response(message="Inbox threads fetched.", data=result)

    async def count_needs_reply(self, current_user: UserContextDto):
        """The sidebar badge: visible threads that need a reply."""
        async with self.database.session() as session:
            count = await self.inbox_thread_service.count_needs_reply(
                session, current_user
            )
        return api_response(message="Inbox count fetched.", data={"needsReply": count})

    async def get_thread(self, current_user: UserContextDto, thread_id: int):
        """One thread with its messages and what the viewer can do."""
        async with self.database.session() as session:
            result = await self.inbox_thread_service.get_thread(
                session, current_user, thread_id
            )
        return api_response(message="Inbox thread fetched.", data=result)

    async def reply(
        self,
        current_user: UserContextDto,
        thread_id: int,
        payload: InboxReplyRequestDto,
    ):
        """Send a reply; 409 ``THREAD_CHANGED`` when newer mail arrived."""
        async with self.database.session() as session:
            result = await self.inbox_thread_service.reply(
                session,
                current_user,
                thread_id,
                payload.body,
                payload.last_seen_message_id,
            )
        return api_response(message="Reply sent.", data=result)

    async def archive(self, current_user: UserContextDto, thread_id: int):
        """Archive a thread."""
        async with self.database.session() as session:
            result = await self.inbox_thread_service.archive(
                session, current_user, thread_id
            )
        return api_response(message="Thread archived.", data=result)

    async def unarchive(self, current_user: UserContextDto, thread_id: int):
        """Bring an archived thread back."""
        async with self.database.session() as session:
            result = await self.inbox_thread_service.unarchive(
                session, current_user, thread_id
            )
        return api_response(message="Thread unarchived.", data=result)

    async def assign(
        self,
        current_user: UserContextDto,
        thread_id: int,
        payload: InboxAssignRequestDto,
    ):
        """Attach a thread to a person and a round or job."""
        async with self.database.session() as session:
            result = await self.inbox_thread_service.assign(
                session,
                current_user,
                thread_id,
                payload.user_id,
                round_id=payload.round_id,
                job_id=payload.job_id,
            )
        return api_response(message="Thread assigned.", data=result)

    async def unassign(self, current_user: UserContextDto, thread_id: int):
        """Remove a thread's assignment."""
        async with self.database.session() as session:
            result = await self.inbox_thread_service.unassign(
                session, current_user, thread_id
            )
        return api_response(message="Assignment removed.", data=result)

    async def move(
        self,
        current_user: UserContextDto,
        thread_id: int,
        payload: InboxMoveRequestDto,
    ):
        """Move a thread to another service.

        ``data`` is null when the viewer cannot see the target service: the
        move happened and the thread has left their Inbox.
        """
        async with self.database.session() as session:
            result = await self.inbox_thread_service.move(
                session, current_user, thread_id, payload.service
            )
        return api_response(message="Thread moved.", data=result)

    async def assign_options(
        self,
        current_user: UserContextDto,
        thread_id: int,
        user_id: int = Query(alias="userId"),
    ):
        """The rounds or jobs a thread could be assigned to for one person."""
        async with self.database.session() as session:
            options = await self.inbox_thread_service.assign_options(
                session, current_user, thread_id, user_id
            )
        unset = {key for key in ("rounds", "jobs") if getattr(options, key) is None}
        return api_response(
            message="Assign options fetched.",
            data=options.model_dump(by_alias=True, mode="json", exclude=unset),
        )

    async def search_people(self, q: str = ""):
        """People to assign a thread to, at most 20."""
        async with self.database.session() as session:
            result = await self.inbox_thread_service.search_people(session, q)
        return api_response(message="People fetched.", data=result)

    async def download_attachment(
        self,
        current_user: UserContextDto,
        thread_id: int,
        message_id: int,
        attachment_id: int,
    ):
        """One attachment of one message of the thread, as a download."""
        async with self.database.session() as session:
            content, name = await self.inbox_thread_service.download_attachment(
                session, current_user, thread_id, message_id, attachment_id
            )
        return Response(
            content=content,
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": _attachment_disposition(name),
                "X-Content-Type-Options": "nosniff",
            },
        )
