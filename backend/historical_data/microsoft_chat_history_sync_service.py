class MicrosoftChatHistorySyncService:
    def __init__(self, logger, microsoft_service, microsoft_chat_message_util):
        """
        Initializes the MicrosoftChatHistorySyncService class.
        Args:
            logger: The logger instance for logging messages.
            microsoft_service: The MicrosoftService instance.
            microsoft_chat_message_util: The MicrosoftChatMessageUtil instance.
        """
        self.logger = logger
        self.microsoft_service = microsoft_service
        self.microsoft_chat_message_util = microsoft_chat_message_util

    async def get_microsoft_chat_messages_by_chat_id(self, chat_id: str):
        """
        Asynchronously fetches all messages in a Microsoft chat by chat ID, yielding pages of messages.

        Args:
            chat_id (str): The unique identifier of the Microsoft chat.

        Yields:
            list: A list of message objects from the current page.
        """
        current_page = await self.microsoft_service.fetch_initial_chat_messages_page(
            chat_id=chat_id
        )
        while current_page:
            messages = current_page.value or []
            if messages:
                yield messages
            next_link = current_page.odata_next_link
            if not next_link:
                break
            current_page = await self.microsoft_service.fetch_chat_messages_by_url(
                chat_id=chat_id, url=next_link
            )

    async def sync_microsoft_chat_messages_by_chat_id(self, chat_id: str) -> dict:
        """
        Asynchronously syncs Microsoft chat messages for a specific chat ID by retrieving the messages in pages,
        processing each page to filter and store the undeleted messages in Redis, and tracking the total processed and
        skipped messages.

        Args:
            chat_id (str): The unique identifier for the Microsoft chat whose messages need to be synced.
        """
        overall_total_processed = 0
        overall_total_skipped = 0
        message_buffer = []
        buffer_count = 10
        count = 0

        all_ldaps = await self.microsoft_service.list_all_id_ldap_mapping()

        async for page_messages in self.get_microsoft_chat_messages_by_chat_id(chat_id):
            if not page_messages:
                self.logger.debug(f"No messages in current page for chat ID: {chat_id}")
                continue
            message_buffer.extend(page_messages)
            count += 1
            if count >= buffer_count:
                messages_count = len(message_buffer)
                self.logger.info(
                    f"Buffer reached {messages_count} messages. Syncing batch to Redis for chat ID: {chat_id}"
                )
                processed_in_batch, skipped_in_batch = (
                    self.microsoft_chat_message_util.sync_history_chat_messages_to_redis(
                        message_buffer, all_ldaps
                    )
                )
                overall_total_processed += processed_in_batch
                overall_total_skipped += skipped_in_batch
                message_buffer = []
                count = 0

        if message_buffer:
            self.logger.info(
                f"Processing remaining {len(message_buffer)} messages in buffer for chat ID: {chat_id}"
            )
            processed_in_batch, skipped_in_batch = (
                self.microsoft_chat_message_util.sync_history_chat_messages_to_redis(
                    message_buffer, all_ldaps
                )
            )
            overall_total_processed += processed_in_batch
            overall_total_skipped += skipped_in_batch

        self.logger.info(
            f"Completed syncing for chat ID: {chat_id}. Total processed: {overall_total_processed}, total skipped: {overall_total_skipped}."
        )
