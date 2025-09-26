from backend.common.constants import CREATED_GOOGLE_CHAT_MESSAGES_INDEX_KEY


class GoogleChatAnalyticsService:
    def __init__(
        self,
        logger,
        redis_client,
        retry_utils,
        date_time_util,
        google_service,
        ldap_service,
    ):
        """
        Initialize the GoogleChatAnalyticsService with necessary clients and logger.

        Args:
            logger: The logger instance for logging messages.
            redis_client: The Redis client instance.
            retry_utils: A RetryUtils for handling retries on transient errors.
            date_time_util: A DateTimeUtil instance for date and time manipulations.
            google_service: A GoogleService instance for interacting with Google APIs (e.g., Google Chat).
            ldap_service: An LdapService instance for interacting with LDAP (e.g., retrieving user information).
        """
        self.logger = logger
        self.redis_client = redis_client
        self.retry_utils = retry_utils
        self.date_time_util = date_time_util
        self.google_service = google_service
        self.ldap_service = ldap_service

    def get_chat_spaces_by_type(self, space_type):
        """
        Retrieve Google Chat spaces filtered by type.

        Args:
            space_type (str): The type of chat spaces to retrieve, e.g., ' SPACE'.

        Raises:
            ValueError: If `space_type` is None or an empty string.

        Returns:
            dict: A dictionary containing chat space information keyed by space ID or name.
        """
        if not space_type:
            raise ValueError("space_type must be provided and cannot be empty.")
        space_dict = self.google_service.get_chat_spaces(space_type=space_type)
        return space_dict

    def count_messages(
        self,
        space_ids: list[str] | None = None,
        sender_ldaps: list[str] | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict[str, dict[str, int]]:
        """
        Count the number of messages in Redis sorted sets for each sender/space
        pair within a specified date range.

        Each Redis key is formatted as CREATED_GOOGLE_CHAT_MESSAGES_INDEX_KEY, representing a
        sorted set where each element corresponds to a message with a UNIX
        timestamp as its score.

        Args:
            space_ids (list[str] | None): List of space IDs whose messages
                should be counted. If None, all available space IDs will be
                retrieved using `google_service.get_chat_spaces()`. Entries with only whitespace
                will be ignored.
            sender_ldaps (list[str] | None): List of sender LDAPs to include
                in the count. If None, all active interns LDAPs will be retrieved
                as the default. Entries with only whitespace will be ignored.
            start_date (str | None): Start date of the range, in "YYYY-MM-DD"
                format.
            end_date (str | None): End date of the range, in "YYYY-MM-DD"
                format.

        Returns:
            dict[str, Any]: Dictionary containing:
                - "start_date" (str): ISO-formatted start date of the range.
                - "end_date" (str): ISO-formatted end date of the range.
                - "result" (dict[str, dict[str, int]]): Nested dictionary mapping
                each sender LDAP to a dictionary that maps each space ID
                to the number of messages sent within the specified date range.
                All sender/space combinations are included, even if the count is zero.

        Example:
            {
                "start_date": "2025-08-01T00:00:00",
                "end_date": "2025-08-31T23:59:59",
                "result": {
                    "alice": {
                        "space1": 25,
                        "space2": 5
                    },
                    "bob": {
                        "space1": 11,
                        "space2": 0
                    }
                }
            }

        TODO:
            Update `get_active_interns_ldaps` to get all active ldaps,
            that stats include all users, not just active interns.
            For now, just keep it consistent with others and use only active interns.
        """

        space_ids = [s.strip() for s in space_ids or [] if s.strip()]
        sender_ldaps = [s.strip() for s in sender_ldaps or [] if s.strip()]
        start_dt, end_dt = self.date_time_util.get_start_end_timestamps(
            start_date, end_date
        )

        if not space_ids:
            self.logger.info("[API] Fetching all space IDs via get_chat_spaces()...")
            space_dict = self.google_service.get_chat_spaces(space_type="SPACE")
            space_ids = list(space_dict.keys())

        if not sender_ldaps:
            self.logger.info(
                "[API] Fetching active interns LDAP as default sender list..."
            )
            sender_ldaps = self.ldap_service.get_active_interns_ldaps()

        pipeline = self.redis_client.pipeline()
        query_keys: list[tuple[str, str]] = []

        for space_id in space_ids:
            for sender_ldap in sender_ldaps:
                redis_key = CREATED_GOOGLE_CHAT_MESSAGES_INDEX_KEY.format(
                    space_id=space_id, sender_ldap=sender_ldap
                )
                pipeline.zcount(redis_key, start_dt.timestamp(), end_dt.timestamp())
                query_keys.append((space_id, sender_ldap))

        pipeline_results = self.retry_utils.get_retry_on_transient(pipeline.execute)
        self.logger.debug(
            f"[API] Redis pipeline executed, received {len(pipeline_results)} results."
        )

        result: dict[str, dict[str, int]] = {}
        for i, (space_id, sender_ldap) in enumerate(query_keys):
            count = pipeline_results[i]
            if sender_ldap not in result:
                result[sender_ldap] = {}

            result[sender_ldap][space_id] = count
        self.logger.info(
            f"[API] Finished processing chat message counts. Returning result with {len(result)} sender entries."
        )

        return {
            "start_date": start_dt.isoformat(),
            "end_date": end_dt.isoformat(),
            "result": result,
        }
