import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from http import HTTPStatus

from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.testclient import TestClient
from starlette.responses import JSONResponse

from backend.common.api_endpoints import (
    EMAIL_MANAGEMENT_ADD_ENDPOINT,
    EMAIL_MANAGEMENT_INITIATE_ENDPOINT,
    EMAIL_MANAGEMENT_LIST_ENDPOINT,
    EMAIL_MANAGEMENT_REMOVE_ENDPOINT,
    EMAIL_MANAGEMENT_SET_PRIMARY_CONFIRM_ENDPOINT,
    EMAIL_MANAGEMENT_SET_PRIMARY_INITIATE_ENDPOINT,
    EMAIL_MANAGEMENT_UNLINK_CONFIRM_ENDPOINT,
    EMAIL_MANAGEMENT_UNLINK_INITIATE_ENDPOINT,
    EMAIL_MANAGEMENT_VERIFY_ENDPOINT,
)
from backend.authentication.email_management_controller import (
    EmailManagementController,
)
from backend.dto.emails_view_dto import EmailEntryDto, EmailsViewDto, IdentityDto


class _FakeSessionContext:
    async def __aenter__(self):
        return MagicMock()

    async def __aexit__(self, *args):
        return False


class TestEmailManagementController(unittest.TestCase):
    def setUp(self):
        self.service = MagicMock()
        self.service.initiate = AsyncMock(return_value={"state": "signed.jwt"})
        self.service.verify = AsyncMock(
            return_value={"ok": True, "email": "alice@gmail.com"}
        )
        self.service.add_email = AsyncMock(
            return_value={"ok": True, "email": "backup@gmail.com"}
        )
        self.service.remove_email = AsyncMock(return_value={"ok": True})
        self.service.initiate_set_primary = AsyncMock(
            return_value={"state": "signed.jwt"}
        )
        self.service.confirm_set_primary = AsyncMock(return_value={"ok": True})
        self.service.initiate_unlink = AsyncMock(return_value={"state": "signed.jwt"})
        self.service.confirm_unlink = AsyncMock(return_value={"ok": True})
        self.service.list_emails_and_identities = AsyncMock(
            return_value=EmailsViewDto(
                emails=[
                    EmailEntryDto(
                        email_id=12,
                        email="alice@gmail.com",
                        otp_confirmed=True,
                        is_primary=True,
                        added_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                        linked_identity_count=1,
                    )
                ],
                internal_identities=[],
                external_identities=[
                    IdentityDto(
                        identity_id=7,
                        subject_identifier="google-oauth2|primary",
                        email_claim="alice@gmail.com",
                        last_used_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
                    )
                ],
            )
        )
        database = MagicMock()
        database.session.return_value = _FakeSessionContext()

        self.controller = EmailManagementController(
            email_management_service=self.service, database=database
        )
        self.app = FastAPI()
        self.app.include_router(self.controller.router)

        self.patcher = patch(
            "backend.authentication.email_management_controller.api_response"
        )
        self.mock_api_response = self.patcher.start()

        def side_effect(data, message, status_code=HTTPStatus.OK):
            return JSONResponse(
                content=jsonable_encoder({"message": message, "data": data}),
                status_code=status_code,
            )

        self.mock_api_response.side_effect = side_effect

    def tearDown(self):
        self.patcher.stop()

    def _client_with_user(self, user_id=42, sub="google-oauth2|primary"):
        mock_user = MagicMock()
        mock_user.user_id = user_id
        mock_user.sub = sub

        @self.app.middleware("http")
        async def _inject_user(request: Request, call_next):
            request.state.user = mock_user
            return await call_next(request)

        return TestClient(self.app)

    def test_initiate_passes_session_user_and_email_to_service(self):
        client = self._client_with_user()
        response = client.post(
            EMAIL_MANAGEMENT_INITIATE_ENDPOINT, json={"email": "alice@gmail.com"}
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.json()["data"], {"state": "signed.jwt"})
        _, kwargs = self.service.initiate.call_args
        self.assertEqual(kwargs["current_user_id"], 42)
        self.assertEqual(kwargs["current_sub"], "google-oauth2|primary")
        self.assertEqual(kwargs["email"], "alice@gmail.com")

    def test_add_email_passes_session_user_and_email_to_service(self):
        client = self._client_with_user()
        response = client.post(
            EMAIL_MANAGEMENT_ADD_ENDPOINT, json={"email": "backup@gmail.com"}
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.json()["data"]["email"], "backup@gmail.com")
        _, kwargs = self.service.add_email.call_args
        self.assertEqual(kwargs["current_user_id"], 42)
        self.assertEqual(kwargs["email"], "backup@gmail.com")

    def test_remove_email_passes_session_user_and_email_id_to_service(self):
        client = self._client_with_user()
        response = client.delete(EMAIL_MANAGEMENT_REMOVE_ENDPOINT.format(email_id=12))

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.json()["data"], {"ok": True})
        _, kwargs = self.service.remove_email.call_args
        self.assertEqual(kwargs["current_user_id"], 42)
        self.assertEqual(kwargs["email_id"], 12)

    def test_remove_email_requires_authentication(self):
        client = TestClient(self.app, raise_server_exceptions=False)
        response = client.delete(EMAIL_MANAGEMENT_REMOVE_ENDPOINT.format(email_id=12))
        self.assertEqual(response.status_code, HTTPStatus.UNAUTHORIZED)

    def test_verify_passes_state_and_otp_to_service(self):
        client = self._client_with_user()
        response = client.post(
            EMAIL_MANAGEMENT_VERIFY_ENDPOINT,
            json={"state": "signed.jwt", "otp": "123456"},
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.json()["data"]["email"], "alice@gmail.com")
        _, kwargs = self.service.verify.call_args
        self.assertEqual(kwargs["current_user_id"], 42)
        self.assertEqual(kwargs["state"], "signed.jwt")
        self.assertEqual(kwargs["otp"], "123456")

    def test_list_emails_passes_session_user_to_service(self):
        client = self._client_with_user()
        response = client.get(EMAIL_MANAGEMENT_LIST_ENDPOINT)

        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = response.json()["data"]

        # Keys serialize to camelCase via the BaseDto alias generator.
        email = data["emails"][0]
        self.assertEqual(email["emailId"], 12)
        self.assertEqual(email["email"], "alice@gmail.com")
        self.assertTrue(email["otpConfirmed"])
        self.assertTrue(email["isPrimary"])
        self.assertEqual(email["linkedIdentityCount"], 1)

        self.assertEqual(data["internalIdentities"], [])
        ext = data["externalIdentities"][0]
        self.assertEqual(ext["identityId"], 7)
        self.assertIsNotNone(ext["lastUsedAt"])

        _, kwargs = self.service.list_emails_and_identities.call_args
        self.assertEqual(kwargs["current_user_id"], 42)
        self.assertEqual(kwargs["current_sub"], "google-oauth2|primary")

    def test_set_primary_initiate_passes_session_user_and_email_id(self):
        client = self._client_with_user()
        response = client.post(
            EMAIL_MANAGEMENT_SET_PRIMARY_INITIATE_ENDPOINT.format(email_id=18)
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.json()["data"], {"state": "signed.jwt"})
        _, kwargs = self.service.initiate_set_primary.call_args
        self.assertEqual(kwargs["current_user_id"], 42)
        self.assertEqual(kwargs["email_id"], 18)

    def test_set_primary_confirm_passes_state_code_and_email_id(self):
        client = self._client_with_user()
        response = client.post(
            EMAIL_MANAGEMENT_SET_PRIMARY_CONFIRM_ENDPOINT.format(email_id=18),
            json={"state": "signed.jwt", "code": "123456"},
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.json()["data"], {"ok": True})
        _, kwargs = self.service.confirm_set_primary.call_args
        self.assertEqual(kwargs["current_user_id"], 42)
        self.assertEqual(kwargs["email_id"], 18)
        self.assertEqual(kwargs["state"], "signed.jwt")
        self.assertEqual(kwargs["code"], "123456")

    def test_set_primary_initiate_requires_authentication(self):
        client = TestClient(self.app, raise_server_exceptions=False)
        response = client.post(
            EMAIL_MANAGEMENT_SET_PRIMARY_INITIATE_ENDPOINT.format(email_id=18)
        )
        self.assertEqual(response.status_code, HTTPStatus.UNAUTHORIZED)

    def test_unlink_initiate_passes_session_user_and_identity_id(self):
        client = self._client_with_user()
        response = client.post(
            EMAIL_MANAGEMENT_UNLINK_INITIATE_ENDPOINT.format(identity_id=7)
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.json()["data"], {"state": "signed.jwt"})
        _, kwargs = self.service.initiate_unlink.call_args
        self.assertEqual(kwargs["current_user_id"], 42)
        self.assertEqual(kwargs["current_sub"], "google-oauth2|primary")
        self.assertEqual(kwargs["identity_id"], 7)

    def test_unlink_confirm_passes_state_code_and_identity_id(self):
        client = self._client_with_user()
        response = client.post(
            EMAIL_MANAGEMENT_UNLINK_CONFIRM_ENDPOINT.format(identity_id=7),
            json={"state": "signed.jwt", "code": "123456"},
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.json()["data"], {"ok": True})
        _, kwargs = self.service.confirm_unlink.call_args
        self.assertEqual(kwargs["current_user_id"], 42)
        self.assertEqual(kwargs["current_sub"], "google-oauth2|primary")
        self.assertEqual(kwargs["identity_id"], 7)
        self.assertEqual(kwargs["state"], "signed.jwt")
        self.assertEqual(kwargs["code"], "123456")

    def test_unlink_initiate_requires_authentication(self):
        client = TestClient(self.app, raise_server_exceptions=False)
        response = client.post(
            EMAIL_MANAGEMENT_UNLINK_INITIATE_ENDPOINT.format(identity_id=7)
        )
        self.assertEqual(response.status_code, HTTPStatus.UNAUTHORIZED)

    def test_unlink_confirm_requires_authentication(self):
        client = TestClient(self.app, raise_server_exceptions=False)
        response = client.post(
            EMAIL_MANAGEMENT_UNLINK_CONFIRM_ENDPOINT.format(identity_id=7),
            json={"state": "signed.jwt", "code": "123456"},
        )
        self.assertEqual(response.status_code, HTTPStatus.UNAUTHORIZED)

    def test_list_emails_requires_authentication(self):
        client = TestClient(self.app, raise_server_exceptions=False)
        response = client.get(EMAIL_MANAGEMENT_LIST_ENDPOINT)
        self.assertEqual(response.status_code, HTTPStatus.UNAUTHORIZED)

    def test_requires_authentication(self):
        client = TestClient(self.app, raise_server_exceptions=False)
        response = client.post(
            EMAIL_MANAGEMENT_INITIATE_ENDPOINT, json={"email": "alice@gmail.com"}
        )
        self.assertEqual(response.status_code, HTTPStatus.UNAUTHORIZED)


if __name__ == "__main__":
    unittest.main()
