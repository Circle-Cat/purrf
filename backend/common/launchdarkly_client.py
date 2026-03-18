import os
import ldclient
from ldclient import Context
from ldclient.config import Config
from backend.common.environment_constants import LAUNCHDARKLY_SDK_KEY
from backend.dto.user_context_dto import UserContextDto
from typing import Any


class LaunchDarklyClient:
    """
    Wrapper around the LaunchDarkly Python Server SDK.

    Provides methods for evaluating feature flags with user context.
    If the SDK key is not set, runs in offline mode where all
    evaluations return their default values.

    Usage:
        client = LaunchDarklyClient(logger)
        client.initialize()   # Call during app startup
        ...
        client.close()        # Call during app shutdown
    """

    def __init__(self, logger):
        self.logger = logger
        self._client = None

    def initialize(self) -> None:
        """
        Connect to LaunchDarkly.

        Reads the SDK key from the environment and initializes the SDK.
        If the key is not set, runs in offline mode.
        """
        sdk_key = os.getenv(LAUNCHDARKLY_SDK_KEY)

        if not sdk_key:
            self.logger.warning(
                "LaunchDarkly SDK key (%s) not set. Feature flags will return default values.",
                LAUNCHDARKLY_SDK_KEY,
            )
            ldclient.set_config(Config(sdk_key="offline", offline=True))
        else:
            ldclient.set_config(Config(sdk_key))
            if ldclient.get().is_initialized():
                self.logger.info("LaunchDarkly client initialized successfully.")
            else:
                self.logger.error("LaunchDarkly client failed to initialize.")

        self._client = ldclient.get()

    def variation(
        self, flag_key: str, user_context: UserContextDto, default_value: Any
    ) -> Any:
        """
        Evaluate a feature flag for a given user context.

        Args:
            flag_key: The LaunchDarkly flag key.
            user_context: UserContextDto from request.state.user.
            default_value: Fallback value if flag cannot be evaluated.

        Returns:
            The flag variation value, or default_value on failure.
        """
        if self._client is None:
            self.logger.warning(
                "LaunchDarkly client not initialized. Returning default value for flag '%s'.",
                flag_key,
            )
            return default_value

        if not user_context.sub:
            self.logger.error(
                "User context key is required for flag evaluation. Returning default value for flag '%s'.",
                flag_key,
            )
            return default_value

        context = (
            Context.builder(user_context.sub)
            .kind("user")
            .set("email", user_context.primary_email or "")
            .build()
        )
        return self._client.variation(flag_key, context, default_value)

    def close(self) -> None:
        """Shut down the LaunchDarkly client gracefully."""
        if self._client is not None:
            self._client.close()
