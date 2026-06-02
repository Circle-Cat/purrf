import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.responses import JSONResponse

from backend.common.api_endpoints import (
    EMAIL_MANAGEMENT_INITIATE_ENDPOINT,
    EMAIL_MANAGEMENT_VERIFY_ENDPOINT,
)
from backend.authentication.email_management_controller import (
    EmailManagementController,
)


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
            return_value={"ok": True, "linked_sub": "email|abc"}
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
                content={"message": message, "data": data}, status_code=status_code
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

    def test_verify_passes_state_and_otp_to_service(self):
        client = self._client_with_user()
        response = client.post(
            EMAIL_MANAGEMENT_VERIFY_ENDPOINT,
            json={"state": "signed.jwt", "otp": "123456"},
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.json()["data"]["linked_sub"], "email|abc")
        _, kwargs = self.service.verify.call_args
        self.assertEqual(kwargs["current_user_id"], 42)
        self.assertEqual(kwargs["state"], "signed.jwt")
        self.assertEqual(kwargs["otp"], "123456")

    def test_requires_authentication(self):
        client = TestClient(self.app, raise_server_exceptions=False)
        response = client.post(
            EMAIL_MANAGEMENT_INITIATE_ENDPOINT, json={"email": "alice@gmail.com"}
        )
        self.assertEqual(response.status_code, HTTPStatus.UNAUTHORIZED)


if __name__ == "__main__":
    unittest.main()
