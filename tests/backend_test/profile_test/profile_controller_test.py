import unittest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime
from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from fastapi.encoders import jsonable_encoder

from backend.common.api_endpoints import MY_PROFILE_ENDPOINT
from backend.profile.profile_controller import ProfileController
from backend.dto.user_context_dto import UserContextDto
from backend.dto.profile_dto import ProfileDto
from backend.dto.users_dto import UsersDto
from backend.common.mentorship_enums import UserTimezone, CommunicationMethod
from backend.common.constants import ProfileField


class TestProfileController(unittest.TestCase):
    def setUp(self):
        self.mock_profile_service = MagicMock()
        self.mock_database = MagicMock()

        self.controller = ProfileController(
            profile_service=self.mock_profile_service,
            database=self.mock_database,
        )

        self.app = FastAPI()
        self.app.include_router(self.controller.router)

        self.patcher = patch("backend.profile.profile_controller.api_response")
        self.mock_api_response = self.patcher.start()

        def api_response_side_effect(*, message, data=None, status_code=HTTPStatus.OK):
            return {
                "message": message,
                "data": data,
                "status_code": status_code,
            }

        self.mock_api_response.side_effect = api_response_side_effect

    def tearDown(self):
        self.patcher.stop()

    def _get_client_with_mock_user(self):
        mock_user = UserContextDto(
            sub="sub-123",
            primary_email="user@example.com",
            roles=["user"],
        )

        @self.app.middleware("http")
        async def mock_auth_middleware(request: Request, call_next):
            request.state.user = mock_user
            return await call_next(request)

        return TestClient(self.app)

    def _make_profile_dto(self) -> ProfileDto:
        user_dto = UsersDto(
            id=1,
            first_name="Alice",
            last_name="Smith",
            timezone=UserTimezone.AMERICA_LOS_ANGELES,
            communication_method=CommunicationMethod.EMAIL,
            timezone_updated_at=datetime.now(),
            updated_timestamp=datetime.now(),
            primary_email="alice@example.com",
            preferred_name="Ally",
            alternative_emails=[],
            linkedin_link=None,
        )

        return ProfileDto(
            id=1,
            user=user_dto,
            training=[],
            work_history=[],
            education=[],
        )

    def test_get_my_profile_success(self):
        client = self._get_client_with_mock_user()

        mock_profile = self._make_profile_dto()

        async_session_mock = AsyncMock()
        self.mock_database.session.return_value.__aenter__.return_value = (
            async_session_mock
        )

        self.mock_profile_service.get_profile = AsyncMock(return_value=mock_profile)

        response = client.get(MY_PROFILE_ENDPOINT)
        response_json = response.json()

        expected_data = {"profile": jsonable_encoder(mock_profile)}

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response_json["message"], "Profile retrieved successfully")
        self.assertEqual(response_json["data"], expected_data)
        self.mock_api_response.assert_called_once()

    def test_get_my_profile_with_fields(self):
        client = self._get_client_with_mock_user()

        mock_profile = self._make_profile_dto()

        async_session_mock = AsyncMock()
        self.mock_database.session.return_value.__aenter__.return_value = (
            async_session_mock
        )

        self.mock_profile_service.get_profile = AsyncMock(return_value=mock_profile)

        response = client.get(f"{MY_PROFILE_ENDPOINT}?fields=training,education")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.mock_profile_service.get_profile.assert_called_once()
        _, _, fields_set = self.mock_profile_service.get_profile.call_args[0]
        self.assertEqual(fields_set, {ProfileField.TRAINING, ProfileField.EDUCATION})

    def test_get_my_profile_missing_user_state(self):
        """
        authenticate() should reject request → 401
        """
        client = TestClient(self.app, raise_server_exceptions=False)

        response = client.get(MY_PROFILE_ENDPOINT)

        self.assertEqual(response.status_code, HTTPStatus.UNAUTHORIZED)


if __name__ == "__main__":
    unittest.main()
