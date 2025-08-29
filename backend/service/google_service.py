class GoogleService:
    """Service class for interacting with Google APIs."""

    def __init__(self, logger, google_chat_client, retry_utils):
        """
        Initializes the GoogleService with necessary clients and logger.

        Args:
            logger (logging.Logger): Logger instance for structured logging.
            google_chat_client: Authenticated Google Chat client.
            retry_utils: A RetryUtils for handling retries on transient errors.
        """
        self.logger = logger
        self.google_chat_client = google_chat_client
        self.retry_utils = retry_utils

    def get_chat_spaces(self, space_type: str) -> dict:
        """Retrieves a dictionary of Google Chat spaces with their display names.

        Args:
            space_type (str): The type of spaces to filter (e.g., SPACE, ROOM).

        Returns:
            dict: A dictionary where keys are space IDs and values are display names.

        Examples:
            {
                "BBBA9AJg-Ty": "CircleCat Mentorship Program,
                "BVDL3CTY-AD": "Engineering Team Chat"
            }
        Raises:
            ValueError: If the API response contains no valid space information.
            RuntimeError: If an error occurs during the API call.
        """
        space_display_names = {}
        page_token = None

        while True:
            req = self.google_chat_client.spaces().list(
                filter=f'space_type = "{space_type}"',
                pageToken=page_token,
            )
            try:
                response = self.retry_utils.get_retry_on_transient(req.execute)

            except Exception as e:
                self.logger.error(
                    "External API error when fetching chat spaces (type=%s, page_token=%s): %s",
                    space_type,
                    page_token,
                    e,
                    exc_info=True,
                )
                raise RuntimeError(
                    "Unable to fetch chat spaces, external API error"
                ) from e

            spaces = response.get("spaces")
            if not spaces:
                raise ValueError(
                    "Google Chat API response missing 'spaces' field in method get_chat_spaces"
                )

            for space in spaces:
                space_id = space.get("name").split("/")[1]
                display_name = space.get("displayName")
                space_display_names[space_id] = display_name

            page_token = response.get("nextPageToken")
            if not page_token:
                break

        count = len(space_display_names)
        self.logger.info(f"Retrieved {count} {space_type} type Chat spaces.")
        return space_display_names
