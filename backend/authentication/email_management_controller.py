"""
Email management routes, mounted under /api/auth/emails:

- ``POST /initiate`` — start an Auth0 passwordless OTP and return a signed state
  JWT binding the code to the caller's session.
- ``POST /verify``   — confirm the OTP, link the new identity, and record the
  address as a confirmed contact.

The caller's user_id is resolved by AuthMiddleware (bootstrap) and read from the
request context, so these handlers do not look the user up again.
"""

from fastapi import APIRouter

from backend.common.api_endpoints import (
    EMAIL_MANAGEMENT_INITIATE_ENDPOINT,
    EMAIL_MANAGEMENT_LIST_ENDPOINT,
    EMAIL_MANAGEMENT_SET_PRIMARY_CONFIRM_ENDPOINT,
    EMAIL_MANAGEMENT_SET_PRIMARY_INITIATE_ENDPOINT,
    EMAIL_MANAGEMENT_UNLINK_CONFIRM_ENDPOINT,
    EMAIL_MANAGEMENT_UNLINK_INITIATE_ENDPOINT,
    EMAIL_MANAGEMENT_VERIFY_ENDPOINT,
)
from backend.common.fast_api_response_wrapper import api_response
from backend.dto.email_management_dto import (
    InitiateRequest,
    OtpConfirmRequest,
    VerifyRequest,
)
from backend.dto.emails_view_dto import EmailsViewDto
from backend.dto.user_context_dto import UserContextDto
from backend.utils.permission_decorators import authenticate


class EmailManagementController:
    def __init__(self, email_management_service, database):
        """
        Initialize the EmailManagementController and register its routes.

        Args:
            email_management_service (EmailManagementService): Service driving the
                OTP initiate/verify flow.
            database (Database): Provides the async session used per request.
        """
        self._service = email_management_service
        self._database = database
        self.router = APIRouter(tags=["email-management"])
        self.router.add_api_route(
            EMAIL_MANAGEMENT_INITIATE_ENDPOINT,
            endpoint=authenticate()(self.initiate),
            methods=["POST"],
            response_model=None,
        )
        self.router.add_api_route(
            EMAIL_MANAGEMENT_VERIFY_ENDPOINT,
            endpoint=authenticate()(self.verify),
            methods=["POST"],
            response_model=None,
        )
        self.router.add_api_route(
            EMAIL_MANAGEMENT_LIST_ENDPOINT,
            endpoint=authenticate()(self.list_emails),
            methods=["GET"],
            response_model=None,
        )
        self.router.add_api_route(
            EMAIL_MANAGEMENT_SET_PRIMARY_INITIATE_ENDPOINT,
            endpoint=authenticate()(self.set_primary_initiate),
            methods=["POST"],
            response_model=None,
        )
        self.router.add_api_route(
            EMAIL_MANAGEMENT_SET_PRIMARY_CONFIRM_ENDPOINT,
            endpoint=authenticate()(self.set_primary_confirm),
            methods=["POST"],
            response_model=None,
        )
        self.router.add_api_route(
            EMAIL_MANAGEMENT_UNLINK_INITIATE_ENDPOINT,
            endpoint=authenticate()(self.unlink_initiate),
            methods=["POST"],
            response_model=None,
        )
        self.router.add_api_route(
            EMAIL_MANAGEMENT_UNLINK_CONFIRM_ENDPOINT,
            endpoint=authenticate()(self.unlink_confirm),
            methods=["POST"],
            response_model=None,
        )

    async def unlink_initiate(self, current_user: UserContextDto, identity_id: int):
        """
        Start a step-up-OTP unlink of one of the caller's sign-in identities.

        Empty-bodied POST: the path's ``identity_id`` is the whole request. The
        service validates the identity can be unlinked, then sends an OTP to the
        *current primary* and returns a signed state snapshotting that primary.

        Args:
            current_user (UserContextDto): The authenticated user context.
            identity_id (int): Primary key of the identity to unlink, from the path.

        Returns:
            A standardized API response wrapping the signed unlink state.
        """
        async with self._database.session() as session:
            data = await self._service.initiate_unlink(
                session=session,
                current_user_id=current_user.user_id,
                current_sub=current_user.sub,
                identity_id=identity_id,
            )
        return api_response(message="OTP sent to primary email", data=data)

    async def unlink_confirm(
        self,
        current_user: UserContextDto,
        identity_id: int,
        body: OtpConfirmRequest,
    ):
        """
        Confirm the step-up OTP, unlink the sign-in identity, and drop its
        synced contact email when nothing else uses it.

        The service validates the signed state against the path's ``identity_id``,
        rechecks the primary has not changed since initiate, verifies the OTP,
        unlinks from Auth0, deletes the identity row, then deletes the matching
        contact email when no surviving identity claims it, and reverse-syncs the
        Auth0 alias index.

        Args:
            current_user (UserContextDto): The authenticated user context.
            identity_id (int): Primary key of the identity to unlink, from the path.
            body (UnlinkConfirmRequest): The signed state and the OTP code.

        Returns:
            A standardized API response confirming the unlink.
        """
        async with self._database.session() as session:
            data = await self._service.confirm_unlink(
                session=session,
                current_user_id=current_user.user_id,
                current_sub=current_user.sub,
                identity_id=identity_id,
                state=body.state,
                code=body.code,
            )
        return api_response(message="Sign-in method removed", data=data)

    async def set_primary_initiate(self, current_user: UserContextDto, email_id: int):
        """
        Start a step-up-OTP switch of the primary contact email.

        Empty-bodied POST: the path's ``email_id`` is the whole request. The
        service validates the target is promotable, then sends an OTP to the
        *current primary* and returns a signed state snapshotting that primary.

        Args:
            current_user (UserContextDto): The authenticated user context.
            email_id (int): Primary key of the email row to promote, from the path.

        Returns:
            A standardized API response wrapping the signed switch state.
        """
        async with self._database.session() as session:
            data = await self._service.initiate_set_primary(
                session=session,
                current_user_id=current_user.user_id,
                email_id=email_id,
            )
        return api_response(message="OTP sent to primary email", data=data)

    async def set_primary_confirm(
        self,
        current_user: UserContextDto,
        email_id: int,
        body: OtpConfirmRequest,
    ):
        """
        Confirm the step-up OTP and swap the primary contact email.

        The service validates the signed state against the path's ``email_id``,
        rechecks the primary has not changed since initiate, verifies the OTP,
        and swaps the primary flag.

        Args:
            current_user (UserContextDto): The authenticated user context.
            email_id (int): Primary key of the email row to promote, from the path.
            body (OtpConfirmRequest): The signed state and the OTP code.

        Returns:
            A standardized API response confirming the swap.
        """
        async with self._database.session() as session:
            data = await self._service.confirm_set_primary(
                session=session,
                current_user_id=current_user.user_id,
                email_id=email_id,
                state=body.state,
                code=body.code,
            )
        return api_response(message="Primary email updated", data=data)

    async def list_emails(self, current_user: UserContextDto):
        """
        Retrieve the caller's comprehensive email and identity view.

        Backs the Settings page: returns every one of the caller's email rows
        (each with an app-layer ``linked_identity_count``) alongside the list of
        ``internal_identities`` and the list of ``external_identities``.

        Args:
            current_user (UserContextDto): The authenticated user context.

        Returns:
            A standardized API response wrapping an ``EmailsViewDto``.
        """
        async with self._database.session() as session:
            result: EmailsViewDto = await self._service.list_emails_and_identities(
                session=session,
                current_user_id=current_user.user_id,
                current_sub=current_user.sub,
            )
        return api_response(message="Emails and identities", data=result)

    async def initiate(self, current_user: UserContextDto, body: InitiateRequest):
        """
        Start email confirmation: send an OTP and return the signed state JWT.

        The caller is resolved by AuthMiddleware; only the email comes from the
        request body.

        Args:
            current_user (UserContextDto): The authenticated caller.
            body (InitiateRequest): Carries the email address to confirm.

        Returns:
            The api_response envelope wrapping the signed state JWT.
        """
        async with self._database.session() as session:
            data = await self._service.initiate(
                session=session,
                current_user_id=current_user.user_id,
                current_sub=current_user.sub,
                email=body.email,
            )
        return api_response(message="OTP sent", data=data)

    async def verify(self, current_user: UserContextDto, body: VerifyRequest):
        """
        Confirm the OTP, link the new identity, and record the confirmed address.

        The address verified is bound to the signed state, not the request body.

        Args:
            current_user (UserContextDto): The authenticated caller.
            body (VerifyRequest): Carries the signed state JWT and the OTP code.

        Returns:
            The api_response envelope wrapping the linked-identity result.
        """
        async with self._database.session() as session:
            data = await self._service.verify(
                session=session,
                current_user_id=current_user.user_id,
                current_sub=current_user.sub,
                state=body.state,
                otp=body.otp,
            )
        return api_response(message="Email verified and linked", data=data)
