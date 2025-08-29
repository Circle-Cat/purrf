class GoogleService:
    """Service class for interacting with Google APIs."""

    def __init__(self, logger, google_chat_client, google_people_client, retry_utils):
        """
        Initializes the GoogleService with necessary clients and logger.

        Args:
            logger (logging.Logger): Logger instance for structured logging.
            google_chat_client: Authenticated Google Chat client.
            google_people_client: Authenticated Google People client.
            retry_utils: A RetryUtils for handling retries on transient errors.
        """
        self.logger = logger
        self.google_chat_client = google_chat_client
        self.google_people_client = google_people_client
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

    def list_directory_all_people_ldap(self) -> dict:
        """
        Retrieves a dictionary of sender IDs to LDAP identifiers from the Google People API.

        This function fetches all directory people from the Google People API, extracts their sender IDs and LDAP
        identifiers, and returns them as a dictionary.

        Returns:
            dict: A dictionary mapping sender IDs (str) to LDAP identifiers (str).

        Raises:
            RuntimeError: If an error occurs during the API call.
        """
        directory_people = []
        formatted_people = {}
        page_token = None

        while True:
            req = self.google_people_client.people().listDirectoryPeople(
                readMask="emailAddresses",
                sources=["DIRECTORY_SOURCE_TYPE_DOMAIN_PROFILE"],
                pageToken=page_token,
            )
            try:
                response = self.retry_utils.get_retry_on_transient(req.execute)
            except Exception as e:
                self.logger.error(
                    "Error fetching directory people (page_token=%s): %s",
                    page_token,
                    e,
                    exc_info=True,
                )
                raise RuntimeError("Unable to fetch directory people") from e

            people = response.get("people")
            if people is None:
                continue
            directory_people.extend(people)
            page_token = response.get("nextPageToken")
            if not page_token:
                break

        for person in directory_people:
            email_addresses = person.get("emailAddresses")
            if not email_addresses:
                self.logger.warning(
                    "Person object missing 'emailAddresses', skipping. Person data: %s",
                    person,
                )
                continue

            email_data = email_addresses[0]
            person_id = email_data.get("metadata", {}).get("source", {}).get("id")
            email_value = email_data.get("value")

            if person_id and email_value and "@" in email_value:
                ldap = email_value.split("@")[0]
                formatted_people[person_id] = ldap

        self.logger.info(
            "Successfully retrieved %d directory people from Google Workspace.",
            len(formatted_people),
        )
        return formatted_people

    def fetch_messages_by_spaces_id_paginated(self, space_id):
        """
        Generator that retrieves messages from a specific Google Chat space page by page.

        Args:
            space_id (str): The ID of the Google Chat space to fetch messages from.

        Yields:
            list: A list of message objects (dict) for each page.

        Raises:
            RuntimeError: If unable to fetch messages due to API error.
        """
        page_token = None
        while True:
            req = (
                self.google_chat_client.spaces()
                .messages()
                .list(
                    parent=f"spaces/{space_id}",
                    pageSize=500,
                    pageToken=page_token,
                )
            )
            try:
                response = self.retry_utils.get_retry_on_transient(req.execute)
            except Exception as e:
                self.logger.error(
                    "Error fetching chat messages (page_token=%s): %s",
                    page_token,
                    e,
                    exc_info=True,
                )
                raise RuntimeError("Unable to fetch Google Chat messages") from e
            messages = response.get("messages", [])
            yield messages

            page_token = response.get("nextPageToken")
            if not page_token:
                break
