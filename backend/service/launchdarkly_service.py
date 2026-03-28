from logging import Logger

from backend.common.launchdarkly_client import LaunchDarklyClient
from backend.dto.user_context_dto import UserContextDto


class LaunchDarklyService:
    """
    Centralized service for all LaunchDarkly feature flag interactions.

    Holds flag key constants and provides methods for flag evaluation.
    To add a new feature flag, add a FLAG_* constant and a corresponding method.
    """

    # Flag key constants
    FLAG_MANUAL_SUBMIT_MEETING = "manual-submit-meeting"
    FLAG_CREATE_GOOGLE_MEETING = "create-google-meeting"
    FLAG_VIEW_PERSONAL_SUMMARY = "view-personal-summary"

    def __init__(self, logger: Logger, launchdarkly_client: LaunchDarklyClient) -> None:
        self.logger = logger
        self.launchdarkly_client = launchdarkly_client

    def _is_enabled(
        self, flag_key: str, user_context_dto: UserContextDto, default: bool = False
    ) -> bool:
        """Check if a boolean feature flag is enabled for the given user."""
        return self.launchdarkly_client.variation(flag_key, user_context_dto, default)

    def is_manual_submit_meeting_enabled(
        self, user_context_dto: UserContextDto
    ) -> bool:
        """Check if the manual submit meeting feature is enabled."""
        return self._is_enabled(self.FLAG_MANUAL_SUBMIT_MEETING, user_context_dto)

    def is_create_google_meeting_enabled(
        self, user_context_dto: UserContextDto
    ) -> bool:
        """Check if the create Google meeting feature is enabled."""
        return self._is_enabled(self.FLAG_CREATE_GOOGLE_MEETING, user_context_dto)

    def is_view_personal_summary_enabled(
        self, user_context_dto: UserContextDto
    ) -> bool:
        """Check if the view personal summary feature is enabled."""
        return self._is_enabled(self.FLAG_VIEW_PERSONAL_SUMMARY, user_context_dto)
