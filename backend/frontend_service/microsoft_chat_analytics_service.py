from backend.common.constants import (
    MICROSOFT_CHAT_MESSAGES_INDEX_KEY,
    MicrosoftChatMessagesChangeType,
)


class MicrosoftChatAnalyticsService:
    def __init__(self, logger, redis_client, date_time_util, ldap_service, retry_utils):
        """
        Initializes the MicrosoftChatAnalyticsService.

        Args:
            logger: The logger instance for logging messages.
            redis_client: The Redis client instance.
            date_time_util: A DateTimeUtil instance for handling date and time operations.
            ldap_service: A LdapService instance for performing LDAP lookups.
            retry_utils: A RetryUtils for handling retries on transient errors.
        """
        self.logger = logger
        self.redis_client = redis_client
        self.date_time_util = date_time_util
        self.ldap_service = ldap_service
        self.retry_utils = retry_utils

    def count_microsoft_chat_messages_in_date_range(
        self,
        ldap_list: list[str] | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict[str, str | dict[str, int]]:
        """
        Count Microsoft chat messages per LDAP user within a specified date range.

        If no `ldap_list` is provided, all active interns' and employees' LDAPs will be retrieved
        automatically from LdapService (`get_all_active_interns_and_employees_ldaps`)

        If `start_date` or `end_date` is not provided, they will be determined using
        `date_time_util.get_start_end_timestamps`, which falls back to the default
        time range configured in the utility.

        The method counts messages by querying Redis sorted sets (ZCOUNT) for each
        LDAP in the date range. The Redis keys are formatted using

        `MICROSOFT_CHAT_MESSAGES_INDEX_KEY` with:
            - message_status = MicrosoftChatMessagesChangeType.CREATED
            - sender_ldap = LDAP user

        Args:
            ldap_list (list[str] | None):
                List of LDAP usernames to count messages for.
                - If None or empty, defaults to all active interns.

            start_date (str | None):
                Start date in ISO 8601 format. Defaults to the utility's start date.

            end_date (str | None):
                End date in ISO 8601 format. Defaults to the utility's end date.

        Returns:
            dict: A dictionary containing the actual date range used and message counts:
                {
                    "start_date": "<ISO 8601 UTC start datetime>",
                    "end_date": "<ISO 8601 UTC end datetime>",
                    "result": {
                        "<ldap1>": <count>,
                        "<ldap2>": <count>,
                        ...
                    }
                }

        Example:
            >>> count_microsoft_chat_messages_in_date_range(
            ...     ldap_list=["alice", "bob"],
            ...     start_date="2024-06-01",
            ...     end_date="2024-06-28T"
            ... )
            {
                "start_date": "2024-06-01T00:00:00+00:00",
                "end_date": "2024-06-28T23:59:59.999999+00:00",
                "result": {
                    "alice": 25,
                    "bob": 11
                }
            }
        """
        start_dt_utc, end_dt_utc = self.date_time_util.get_start_end_timestamps(
            start_date, end_date
        )
        start_timestamp = start_dt_utc.timestamp()
        end_timestamp = end_dt_utc.timestamp()
        self.logger.info(f"Date range from {start_dt_utc} to {end_dt_utc}")

        if not ldap_list:
            ldap_list = self.ldap_service.get_all_active_interns_and_employees_ldaps()
            self.logger.info(
                f"Fetched all active interns and employees LDAP, count = {len(ldap_list)}."
            )
        pipeline = self.redis_client.pipeline()
        for ldap in ldap_list:
            redis_key = MICROSOFT_CHAT_MESSAGES_INDEX_KEY.format(
                message_status=MicrosoftChatMessagesChangeType.CREATED.value,
                sender_ldap=ldap,
            )
            pipeline.zcount(redis_key, start_timestamp, end_timestamp)
            self.logger.debug(
                f"ZCOUNT key: {redis_key} for timestamp range: {start_timestamp} - {end_timestamp}"
            )

        counts = self.retry_utils.get_retry_on_transient(pipeline.execute)
        self.logger.debug(f"Redis pipeline zcount results: {counts}")

        result_by_ldap = dict(zip(ldap_list, counts))
        self.logger.debug(f"Final count result: {result_by_ldap}")

        return {
            "start_date": start_dt_utc.isoformat(),
            "end_date": end_dt_utc.isoformat(),
            "result": result_by_ldap,
        }
