from http import HTTPStatus

from fastapi import APIRouter, BackgroundTasks, Query

from backend.common.api_endpoints import (
    MENTORSHIP_ADMIN_EMAIL_SEND_CANCEL,
    MENTORSHIP_ADMIN_EMAIL_SEND_CONFIRM,
    MENTORSHIP_ADMIN_EMAIL_SEND_PREVIEW,
    MENTORSHIP_ADMIN_EMAIL_SENDS,
    MENTORSHIP_ADMIN_EMAIL_SENDS_NOTIFIED,
    MENTORSHIP_ADMIN_KIT_DRAFTS,
)
from backend.common.fast_api_response_wrapper import api_response
from backend.common.permissions import Permission
from backend.dto.mentorship_email_dto import EmailConfirmDto, EmailSendCreateDto
from backend.dto.user_context_dto import UserContextDto
from backend.utils.permission_decorators import authenticate

READ = [Permission.MENTORSHIP_ADMIN_READ]
WRITE = [Permission.MENTORSHIP_ADMIN_WRITE]


class MentorshipEmailController:
    """HTTP layer for mentorship sends through Kit. Rules and commits live in
    MentorshipEmailService; preparation runs in MentorshipEmailPrepareService."""

    def __init__(
        self,
        mentorship_email_service,
        mentorship_email_prepare_service,
        launchdarkly_service,
        database,
    ):
        self.service = mentorship_email_service
        self.prepare_service = mentorship_email_prepare_service
        self.launchdarkly_service = launchdarkly_service
        self.database = database
        self.router = APIRouter(tags=["mentorship-admin-email"])
        routes = [
            (MENTORSHIP_ADMIN_KIT_DRAFTS, "GET", READ, self.list_drafts),
            (MENTORSHIP_ADMIN_EMAIL_SENDS_NOTIFIED, "GET", READ, self.list_notified),
            (MENTORSHIP_ADMIN_EMAIL_SENDS, "POST", WRITE, self.create_send),
            (MENTORSHIP_ADMIN_EMAIL_SEND_PREVIEW, "POST", WRITE, self.refresh_preview),
            (MENTORSHIP_ADMIN_EMAIL_SEND_CONFIRM, "POST", WRITE, self.confirm),
            (MENTORSHIP_ADMIN_EMAIL_SEND_CANCEL, "POST", WRITE, self.cancel),
        ]
        for path, method, permissions, handler in routes:
            self.router.add_api_route(
                path,
                endpoint=authenticate(permissions=permissions)(handler),
                methods=[method],
                response_model=None,
            )

    def _disabled(self, current_user: UserContextDto):
        if self.launchdarkly_service.is_kit_email_enabled(current_user):
            return None
        return api_response(
            message="Not found.", success=False, status_code=HTTPStatus.NOT_FOUND
        )

    async def list_drafts(self, current_user: UserContextDto):
        if (off := self._disabled(current_user)) is not None:
            return off
        data = await self.service.list_drafts()
        return api_response(message="Kit drafts retrieved.", data=data)

    async def list_notified(
        self,
        current_user: UserContextDto,
        background_tasks: BackgroundTasks,
        round_id: int = Query(alias="roundId"),
    ):
        if (off := self._disabled(current_user)) is not None:
            return off
        async with self.database.session() as session:
            data, resume_ids = await self.service.list_notified(session, round_id)
        # Restarts a preparation a killed pod left behind; the lease in
        # claim_for_prepare stops two workers from doing the same send.
        for send_id in resume_ids:
            background_tasks.add_task(self.prepare_service.run, send_id)
        return api_response(message="Notified people retrieved.", data=data)

    async def create_send(self, body: EmailSendCreateDto, current_user: UserContextDto):
        if (off := self._disabled(current_user)) is not None:
            return off
        async with self.database.session() as session:
            data = await self.service.create_send(
                session, body, created_by=current_user.user_id
            )
        return api_response(
            message="Draft created in Kit.", data=data, status_code=HTTPStatus.CREATED
        )

    async def refresh_preview(self, send_id: int, current_user: UserContextDto):
        if (off := self._disabled(current_user)) is not None:
            return off
        async with self.database.session() as session:
            data = await self.service.refresh_preview(session, send_id)
        return api_response(message="Preview refreshed.", data=data)

    async def confirm(
        self,
        send_id: int,
        body: EmailConfirmDto,
        current_user: UserContextDto,
        background_tasks: BackgroundTasks,
    ):
        if (off := self._disabled(current_user)) is not None:
            return off
        async with self.database.session() as session:
            data = await self.service.confirm(session, send_id, body)
        background_tasks.add_task(self.prepare_service.run, send_id)
        return api_response(
            message="Adding recipients in Kit.",
            data=data,
            status_code=HTTPStatus.ACCEPTED,
        )

    async def cancel(self, send_id: int, current_user: UserContextDto):
        if (off := self._disabled(current_user)) is not None:
            return off
        async with self.database.session() as session:
            data = await self.service.cancel(session, send_id)
        return api_response(message="Send cancelled.", data=data)
