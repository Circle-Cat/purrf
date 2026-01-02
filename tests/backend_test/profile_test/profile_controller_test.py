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

    def test_update_my_profile_success(self):
        """Tests successful profile update."""
        client = self._get_client_with_mock_user()
        mock_profile = self._make_profile_dto()

        async_session_mock = AsyncMock()
        self.mock_database.session.return_value.__aenter__.return_value = (
            async_session_mock
        )
        self.mock_profile_service.update_profile = AsyncMock(return_value=mock_profile)

        # Prepare request payload (camelCase to simulate frontend input)
        update_payload = {
            "workHistory": [
                {
                    "title": "Engineer",
                    "companyOrOrganization": "Tech Corp",
                    "startDate": "2020-01-01",
                    "isCurrentJob": True,
                }
            ]
        }

        response = client.patch(MY_PROFILE_ENDPOINT, json=update_payload)
        response_json = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)

        # Verify service was called with correct arguments
        # FastAPI automatically converts JSON into a ProfileCreateDto
        self.mock_profile_service.update_profile.assert_called_once()
        args, kwargs = self.mock_profile_service.update_profile.call_args

        # Verify the passed DTO content
        passed_profile_dto = kwargs.get("profile") or args[2]
        self.assertEqual(
            passed_profile_dto.work_history[0].company_or_organization,
            "Tech Corp",
        )

        # Verify response data
        expected_data = {"profile": jsonable_encoder(mock_profile)}
        self.assertEqual(response_json["data"], expected_data)

    def test_update_my_profile_validation_error(self):
        """Tests that invalid input data results in a 422 Unprocessable Entity response."""
        client = self._get_client_with_mock_user()

        # Prepare an invalid enum value (degree must be a valid Degree)
        invalid_payload = {
            "education": [
                {
                    "degree": "BS",
                    "school": "Northeastern University",
                    "fieldOfStudy": "CS",
                    "startDate": "2020-01-01",
                    "end_date": "2024-01-01",
                }
            ]
        }

        response = client.patch(MY_PROFILE_ENDPOINT, json=invalid_payload)

        # FastAPI returns 422 for Pydantic validation errors by default
        self.assertEqual(response.status_code, HTTPStatus.UNPROCESSABLE_ENTITY)
        self.mock_profile_service.update_profile.assert_not_called()

    def test_update_my_profile_unauthorized(self):
        """Tests that an unauthenticated request returns 401 Unauthorized."""
        client = TestClient(self.app, raise_server_exceptions=False)

        response = client.patch(
            MY_PROFILE_ENDPOINT,
            json={
                "workHistory": [
                    {
                        "title": "Engineer",
                        "companyOrOrganization": "Tech Corp",
                        "startDate": "2020-01-01",
                        "isCurrentJob": True,
                    }
                ]
            },
        )

        self.assertEqual(response.status_code, HTTPStatus.UNAUTHORIZED)
        self.mock_profile_service.update_profile.assert_not_called()


if __name__ == "__main__":
    unittest.main()
