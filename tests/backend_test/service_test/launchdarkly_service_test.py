from unittest import TestCase, main
from unittest.mock import Mock
from backend.service.launchdarkly_service import LaunchDarklyService
from backend.dto.user_context_dto import UserContextDto


class TestLaunchDarklyService(TestCase):
    def setUp(self):
        self.logger = Mock()
        self.ld_client = Mock()
        self.service = LaunchDarklyService(self.logger, self.ld_client)
        self.user = UserContextDto(sub="user-123", primary_email="test@example.com")

    def test__is_enabled_returns_true(self):
        self.ld_client.variation.return_value = True

        result = self.service._is_enabled("feature-flag", self.user)

        self.assertTrue(result)
        self.ld_client.variation.assert_called_once_with(
            "feature-flag", self.user, False
        )

    def test__is_enabled_returns_default_on_failure(self):
        self.ld_client.variation.return_value = True

        self.service._is_enabled("feature-flag", self.user, default=True)

        self.ld_client.variation.assert_called_once_with(
            "feature-flag", self.user, True
        )

    def test_is_manual_submit_meeting_enabled(self):
        self.ld_client.variation.return_value = True

        result = self.service.is_manual_submit_meeting_enabled(self.user)

        self.assertTrue(result)
        self.ld_client.variation.assert_called_once_with(
            "manual-submit-meeting", self.user, False
        )

    def test_is_create_google_meeting_enabled(self):
        self.ld_client.variation.return_value = True

        result = self.service.is_create_google_meeting_enabled(self.user)

        self.assertTrue(result)
        self.ld_client.variation.assert_called_once_with(
            "create-google-meeting", self.user, False
        )


if __name__ == "__main__":
    main()
