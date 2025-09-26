class GoogleChatHistorySyncService:
    def __init__(self, logger, google_service, google_chat_message_utils):
        """
        Initializes the GoogleChatHistorySyncService class.
        Args:
            logger: The logger instance for logging messages.
            google_service: The GoogleService instance.
            google_chat_message_utils: The GoogleChatMessageUtils instance.
        """
        self.logger = logger
        self.google_service = google_service
        self.google_chat_message_utils = google_chat_message_utils

    def sync_history_messages(self) -> int:
        """
        Synchronizes Google Chat history messages into Redis.

        Workflow:
            1. Retrieves all Google Chat spaces of type "SPACE".
            2. Fetches LDAP identifiers for all directory people.
            3. Iterates through each chat space:
                - Retrieves messages in batches using a paginated generator.
                - Stores each batch of messages into Redis via utility helpers.
                - Logs progress and message counts.
            4. Aggregates totals for both processed spaces and processed messages.
            5. Handles and logs unexpected errors.

        Returns:
            int: The total number of chat messages successfully processed.

        Raises:
            ValueError: If no Google Chat spaces of type "SPACE" are found,
                        or if no LDAP mappings are available.
            Exception: Any unexpected error during synchronization is logged
                    and re-raised for higher-level handling.
        """
        self.logger.info("Starting Google Chat history synchronization.")

        try:
            space_display_names = self.google_service.get_chat_spaces("SPACE")
            if not space_display_names:
                raise ValueError("No Google Chat spaces of type 'SPACE' found.")

            all_ldaps_dict = self.google_service.list_directory_all_people_ldap()
            if not all_ldaps_dict:
                raise ValueError("No LDAP mappings found for directory people.")

            total_messages_processed_count = 0
            total_spaces_processed = 0

            for space_id, space_name in space_display_names.items():
                total_spaces_processed += 1
                self.logger.info(
                    "Processing messages for Google Chat space %d/%d: '%s' (ID: %s)",
                    total_spaces_processed,
                    len(space_display_names),
                    space_name,
                    space_id,
                )
                messages_in_current_space = 0

                for (
                    message_batch
                ) in self.google_service.fetch_messages_by_spaces_id_paginated(
                    space_id
                ):
                    if message_batch:
                        self.logger.debug(
                            "Fetched %d messages from space '%s' (ID: %s) for batch processing.",
                            len(message_batch),
                            space_name,
                            space_id,
                        )
                        messages_in_current_space += len(message_batch)
                        total_messages_processed_count += len(message_batch)

                        self.google_chat_message_utils.sync_batch_created_messages(
                            message_batch, all_ldaps_dict
                        )
                    else:
                        self.logger.debug(
                            "No messages found in the current batch for space '%s' (ID: %s).",
                            space_name,
                            space_id,
                        )

                self.logger.info(
                    "Finished processing %d messages from space '%s' (ID: %s).",
                    messages_in_current_space,
                    space_name,
                    space_id,
                )
            self.logger.info(
                "Completed Google Chat history synchronization for %d spaces. Total messages processed (sent for batching): %d.",
                total_spaces_processed,
                total_messages_processed_count,
            )

        except Exception as e:
            self.logger.error(
                "An unexpected error occurred during Google Chat history synchronization: %s",
                e,
                exc_info=True,
            )
            raise
        return total_messages_processed_count
