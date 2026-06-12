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
    EMAIL_MANAGEMENT_VERIFY_ENDPOINT,
)
from backend.common.fast_api_response_wrapper import api_response
from backend.dto.email_management_dto import InitiateRequest, VerifyRequest
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
