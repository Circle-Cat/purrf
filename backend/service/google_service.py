from datetime import datetime

from google.apps import meet_v2
from google.protobuf import field_mask_pb2


class GoogleService:
    """Service class for interacting with Google APIs."""

    def __init__(
        self,
        logger,
        google_chat_client,
        google_people_client,
        google_workspaceevents_client,
        retry_utils,
        google_calendar_client,
        meet_spaces_client,
    ):
        """
        Initializes the GoogleService with necessary clients and logger.

        Args:
            logger (logging.Logger): Logger instance for structured logging.
            google_chat_client: Authenticated Google Chat client.
            google_people_client: Authenticated Google People client.
            google_workspaceevents_client: Authenticated Google Workspace Events client.
            retry_utils: A RetryUtils for handling retries on transient errors.
            google_calendar_client: Authenticated Google Calendar client.
            meet_spaces_client: Authenticated Google Meet SpacesServiceAsyncClient.
        """
        self.logger = logger
        self.google_chat_client = google_chat_client
        self.google_people_client = google_people_client
        self.google_workspaceevents_client = google_workspaceevents_client
        self.retry_utils = retry_utils
        self.google_calendar_client = google_calendar_client
        self.meet_spaces_client = meet_spaces_client

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

    def get_ldap_by_id(self, user_id):
        """
        Retrieves the LDAP identifier (local part of the email) for a given person ID using the Google People API.

        This function fetches the profile of a person identified by their ID and extracts the local part of their
        email address to return as the LDAP identifier.

        Args:
            user_id (str): The unique identifier of the person in the Google People API.

        Returns:
            str or None: The LDAP identifier (local part of the email) if found, otherwise None.

        Raises:
            RuntimeError: If an error occurs during the API call.
        """
        request = self.google_people_client.people().get(
            resourceName=f"people/{user_id}", personFields="emailAddresses"
        )
        try:
            response = self.retry_utils.get_retry_on_transient(request.execute)
        except Exception as e:
            self.logger.error(f"Failed to fetch profile for user {user_id}: {e}")
            raise RuntimeError(
                f"Unexpected error fetching profile for user {user_id}"
            ) from e

        email_addresses = response.get("emailAddresses", [])
        if email_addresses:
            email = email_addresses[0].get("value", "")
            if email and "@" in email:
                local_part = email.split("@")[0]
                self.logger.info(f"Retrieved LDAP '{local_part}' for ID '{user_id}'.")
                return local_part
        self.logger.warning(f"No email found for person ID: {user_id}.")
        return None

    def renew_subscription(self, subscription_name: str):
        """
        Renews a subscription by calling subscriptions.update() of the Workspace Events API.
        Sets the time-to-live (TTL) to 0, which indicates the subscription should not expire.

        Args:
            subscription_name (str): The resource name of the subscription to renew.

        Returns:
            dict: The API response for the patch operation.

        Raises:
            RuntimeError: If the API call fails.
        """
        BODY = {
            "ttl": {"seconds": 0},
        }

        request = self.google_workspaceevents_client.subscriptions().patch(
            name=subscription_name, updateMask="ttl", body=BODY
        )
        try:
            response = self.retry_utils.get_retry_on_transient(request.execute)
            self.logger.info("Renew subscription response: %s", response)
            return response
        except Exception as e:
            self.logger.error(
                "Failed to renew subscription '%s': %s",
                subscription_name,
                e,
                exc_info=True,
            )
            raise RuntimeError(
                f"Failed to renew subscription '{subscription_name}'"
            ) from e

    def insert_google_meeting(
        self,
        summary: str,
        start_time: datetime,
        end_time: datetime,
        attendees_emails: list[str],
        request_id: str,
        event_id: str = None,
    ) -> dict:
        """
        Calls Google Calendar API to create an event with a Meet link.
        """
        event_body = {
            "summary": summary,
            "start": {"dateTime": start_time.isoformat(), "timeZone": "Etc/UTC"},
            "end": {"dateTime": end_time.isoformat(), "timeZone": "Etc/UTC"},
            "attendees": [{"email": email} for email in attendees_emails],
            "conferenceData": {
                "createRequest": {
                    "requestId": request_id,
                    "conferenceSolutionKey": {"type": "hangoutsMeet"},
                }
            },
            "transparency": "opaque",
            "visibility": "default",
        }

        if event_id:
            event_body["id"] = event_id

        req = self.google_calendar_client.events().insert(
            calendarId="primary",
            body=event_body,
            conferenceDataVersion=1,
            sendUpdates="all",
        )
        try:
            response = self.retry_utils.get_retry_on_transient(req.execute)
            self.logger.info(
                "[GoogleService] Successfully created Google Meeting: %s",
                response.get("hangoutLink"),
            )
            return response
        except Exception as e:
            self.logger.error(
                "Failed to create Google Meeting (request_id=%s): %s",
                request_id,
                e,
                exc_info=True,
            )
            raise RuntimeError(
                "Unable to create Google Meeting via Calendar API"
            ) from e

    async def get_meet_space_name(self, meeting_code: str) -> str:
        """
        Resolves the internal Meet space resource name from a meeting code.

        Args:
            meeting_code (str): The Meet meeting code, e.g. "abc-defg-hij".

        Returns:
            str: The space resource name, e.g. "spaces/XXXXXXXXXXXXXXXX".
        """
        try:
            space = await self.retry_utils.get_async_retry_on_transient(
                self.meet_spaces_client.get_space, name=f"spaces/{meeting_code}"
            )
            return space.name
        except Exception as e:
            self.logger.error(
                "[GoogleService] Failed to resolve Meet space for meeting_code=%s: %s",
                meeting_code,
                e,
                exc_info=True,
            )
            raise RuntimeError(
                f"Unable to resolve Meet space for meeting code: {meeting_code}"
            ) from e

    async def update_meet_space_type_to_open(self, space_name: str) -> None:
        """
        Updates a Google Meet space's access type to OPEN.

        Args:
            space_name (str): The Meet space resource name, e.g. "spaces/XXXXXXXXXXXXXXXX".
        """
        request = meet_v2.UpdateSpaceRequest(
            space=meet_v2.Space(
                name=space_name,
                config=meet_v2.SpaceConfig(
                    access_type=meet_v2.SpaceConfig.AccessType.OPEN,
                ),
            ),
            update_mask=field_mask_pb2.FieldMask(paths=["config.access_type"]),
        )
        try:
            await self.retry_utils.get_async_retry_on_transient(
                self.meet_spaces_client.update_space, request=request
            )
            self.logger.info(
                "[GoogleService] Meet space %s access type set to OPEN", space_name
            )
        except Exception as e:
            self.logger.error(
                "[GoogleService] Failed to update Meet space %s to OPEN: %s",
                space_name,
                e,
                exc_info=True,
            )
            raise RuntimeError(
                f"Unable to update Meet space access type: {space_name}"
            ) from e
