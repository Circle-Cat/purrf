from datetime import datetime
from http import HTTPStatus

from google.apps import meet_v2
from google.protobuf import field_mask_pb2
from googleapiclient.errors import HttpError

from backend.common.exceptions import MeetingGoneError

BATCH_DELETE_SIZE = 500


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
        meet_conference_records_client,
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
            meet_conference_records_client: Meet ConferenceRecordsService async client.
        """
        self.logger = logger
        self.google_chat_client = google_chat_client
        self.google_people_client = google_people_client
        self.google_workspaceevents_client = google_workspaceevents_client
        self.retry_utils = retry_utils
        self.google_calendar_client = google_calendar_client
        self.meet_spaces_client = meet_spaces_client
        self.meet_conference_records_client = meet_conference_records_client

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

    def _get_people_email_addresses(self, user_id: str) -> list[dict]:
        """Fetch emailAddresses from the People API for user_id. Raises on failure."""
        request = self.google_people_client.people().get(
            resourceName=f"people/{user_id}", personFields="emailAddresses"
        )
        response = self.retry_utils.get_retry_on_transient(request.execute)
        return response.get("emailAddresses", [])

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
        try:
            email_addresses = self._get_people_email_addresses(user_id)
        except Exception as e:
            self.logger.error(f"Failed to fetch profile for user {user_id}: {e}")
            raise RuntimeError(
                f"Unexpected error fetching profile for user {user_id}"
            ) from e

        if email_addresses:
            email = email_addresses[0].get("value", "")
            if email and "@" in email:
                local_part = email.split("@")[0]
                self.logger.info(f"Retrieved LDAP '{local_part}' for ID '{user_id}'.")
                return local_part
        self.logger.warning(f"No email found for person ID: {user_id}.")
        return None

    def get_email_by_google_user_id(self, google_user_id: str) -> str | None:
        """
        Look up the primary email for a Google user by their numeric user ID.

        Uses the People API with domain-wide delegation, so it works for any
        user inside the organisation. Returns None for external Google accounts
        or if the lookup fails for any reason.
        """
        try:
            email_addresses = self._get_people_email_addresses(google_user_id)
        except Exception as e:
            self.logger.warning(
                "Failed to fetch email for Google user %s: %s", google_user_id, e
            )
            return None
        if email_addresses:
            return email_addresses[0].get("value", "")
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
        calendar_id: str,
        event_id: str = None,
    ) -> dict:
        """
        Calls Google Calendar API to create an event with a Meet link.

        Args:
            summary (str): Event title.
            start_time (datetime): Event start.
            end_time (datetime): Event end.
            attendees_emails (list[str]): Addresses to invite.
            request_id (str): Idempotency key for the Meet conference creation.
            calendar_id (str): The calendar to create the event on. Required and
                without a default on purpose -- Calendar event ids are scoped per
                calendar, so pointing every environment at the account's primary
                calendar is what allowed one environment's delete to remove
                another's event.
            event_id (str | None): Calendar event id to create the event under.
                Supplying one makes the insert idempotent — see
                ``_recover_duplicate_event``.

        Returns:
            dict: The created event (or, after a duplicate-id conflict, the
                event an earlier attempt already created).

        Raises:
            RuntimeError: If the event could neither be created nor recovered.
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
            calendarId=calendar_id,
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
            recovered = self._recover_duplicate_event(e, event_id, calendar_id)
            if recovered is not None:
                self.logger.warning(
                    "[GoogleService] Insert of event_id=%s conflicted but the event "
                    "exists — an earlier attempt succeeded; recovered it "
                    "(request_id=%s)",
                    event_id,
                    request_id,
                )
                return recovered
            self.logger.error(
                "Failed to create Google Meeting (request_id=%s): %s",
                request_id,
                e,
                exc_info=True,
            )
            raise RuntimeError(
                "Unable to create Google Meeting via Calendar API"
            ) from e

    def _recover_duplicate_event(
        self, error: Exception, event_id: str | None, calendar_id: str
    ) -> dict | None:
        """Fetch back the event a duplicate-id conflict refers to, if there is one.

        ``events.insert`` is retried on transient errors, so a lost response can
        leave the event created on Google's side — invitations already mailed,
        because we insert with ``sendUpdates="all"`` — while this client only
        sees a failure. The retry then re-sends the same body, collides with the
        ``event_id`` we minted, and Calendar answers 409 ``duplicate``.

        That 409 is therefore proof the event exists, not a reason to fail: the
        whole point of passing our own ``event_id`` is that the insert is
        idempotent. Failing anyway would leave an event on the calendar that
        never reaches ``mentorship_meeting``, so Purrf can neither show nor
        delete it, while the user is told to retry — producing a second event
        at the same time.

        Args:
            error (Exception): The failure raised by the insert.
            event_id (str | None): The id we asked Calendar to use, if any.
            calendar_id (str): The calendar the conflicting insert targeted. The
                fetch has to read the same calendar the collision happened on --
                the id it collided with only exists there.

        Returns:
            dict | None: The existing event, or None when there is nothing to
                recover — the error was not a 409, we minted no id for it to
                collide with, the fetch failed, or the id belongs to a cancelled
                event (a reused id rather than the event we just tried to
                create). The caller reports failure in every None case.
        """
        if not event_id or not isinstance(error, HttpError):
            return None
        if getattr(error.resp, "status", None) != HTTPStatus.CONFLICT:
            return None

        try:
            event = self.retry_utils.get_retry_on_transient(
                self.google_calendar_client.events()
                .get(calendarId=calendar_id, eventId=event_id)
                .execute
            )
        except Exception as e:
            self.logger.error(
                "[GoogleService] event_id=%s conflicted but could not be fetched "
                "back: %s",
                event_id,
                e,
                exc_info=True,
            )
            return None

        if event.get("status") == "cancelled":
            self.logger.error(
                "[GoogleService] event_id=%s conflicted with a cancelled event; "
                "not treating it as created",
                event_id,
            )
            return None
        return event

    def update_google_meeting(
        self,
        event_id: str,
        start_time: datetime,
        end_time: datetime,
        attendees_emails: list[str],
        calendar_id: str,
    ) -> dict:
        """Move an existing event and/or replace its attendee list.

        Patches **only** ``start`` / ``end`` / ``attendees``. ``conferenceData``
        is deliberately absent from the body: including it would mint a new
        conference and invalidate the Meet link already mailed to the
        attendees, which is the whole reason we patch instead of
        delete-and-recreate.

        ``sendUpdates="all"`` makes Google mail everyone the change — an
        attendee dropped from the list gets a cancellation, a new one gets an
        invitation. Unlike ``insert``, patch is naturally idempotent (the same
        body applied twice yields the same event), so it needs no
        client-minted id or duplicate recovery.

        Args:
            event_id (str): The Calendar event to patch.
            start_time (datetime): New start, tz-aware.
            end_time (datetime): New end, tz-aware.
            attendees_emails (list[str]): The complete attendee list after the
                change (not a delta).
            calendar_id (str): The calendar holding the event. Required and
                without a default: unlike a delete, a patch aimed at the wrong
                calendar does not quietly 404 -- if the id exists there it moves
                that event and mails everyone the change.

        Returns:
            dict: The patched event.

        Raises:
            MeetingGoneError: The event is absent (404) or deleted (410).
            RuntimeError: Any other failure.
        """
        req = self.google_calendar_client.events().patch(
            calendarId=calendar_id,
            eventId=event_id,
            body={
                "start": {"dateTime": start_time.isoformat(), "timeZone": "Etc/UTC"},
                "end": {"dateTime": end_time.isoformat(), "timeZone": "Etc/UTC"},
                "attendees": [{"email": email} for email in attendees_emails],
            },
            sendUpdates="all",
        )
        try:
            response = self.retry_utils.get_retry_on_transient(req.execute)
            self.logger.info(
                "[GoogleService] Patched Google Meeting event_id=%s", event_id
            )
            return response
        except HttpError as e:
            status = getattr(e.resp, "status", None)
            if status in (HTTPStatus.NOT_FOUND, HTTPStatus.GONE):
                self.logger.error(
                    "[GoogleService] Cannot patch event_id=%s: it is gone (status=%s)",
                    event_id,
                    status,
                )
                raise MeetingGoneError(
                    f"Calendar event {event_id} no longer exists"
                ) from e
            self.logger.error(
                "[GoogleService] Failed to patch event_id=%s: %s",
                event_id,
                e,
                exc_info=True,
            )
            raise RuntimeError(
                "Unable to update Google Meeting via Calendar API"
            ) from e
        except Exception as e:
            self.logger.error(
                "[GoogleService] Failed to patch event_id=%s: %s",
                event_id,
                e,
                exc_info=True,
            )
            raise RuntimeError(
                "Unable to update Google Meeting via Calendar API"
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

    async def list_ended_conferences(
        self, end_time_after: str, end_time_before: str
    ) -> list[dict]:
        """
        Lists conference records that ended within the given time window.

        Args:
            end_time_after (str): ISO 8601 lower bound for the conference end time (inclusive).
            end_time_before (str): ISO 8601 upper bound for the conference end time (inclusive).

        Returns:
            list[dict]: A list of conference records, each containing:
                - name (str): Resource name (e.g., "conferenceRecords/xxx").
                - start_time (str): Start time in ISO 8601 format, or "" if unavailable.
                - end_time (str): End time in ISO 8601 format, or "" if unavailable.
                - space (str): Meet space resource name (e.g., "spaces/abc-defg-hij").
        """
        self.logger.debug(
            "[GoogleService] list_ended_conferences: after=%s, before=%s",
            end_time_after,
            end_time_before,
        )
        conferences = []
        request = meet_v2.ListConferenceRecordsRequest(
            filter=f'end_time>="{end_time_after}" AND end_time<="{end_time_before}"',
        )
        pager = await self.meet_conference_records_client.list_conference_records(
            request=request
        )
        async for record in pager:
            conferences.append({
                "name": record.name,
                "space": record.space,
                "start_time": record.start_time.isoformat()
                if record.start_time
                else "",
                "end_time": record.end_time.isoformat() if record.end_time else "",
            })
        self.logger.debug(
            "[GoogleService] list_ended_conferences: fetched %d records",
            len(conferences),
        )
        return conferences

    async def list_conferences_by_meeting_code(
        self, meeting_code: str, start_time_after: str, start_time_before: str
    ) -> list[dict]:
        """
        Lists conference records for one Meet space, by its meeting code.

        The reverse of ``list_ended_conferences``: instead of pulling every
        conference the service account can see and discarding the ones that
        are not ours, this asks for exactly one meeting's records.
        ``ListConferenceRecordsRequest.filter`` supports ``space.meeting_code``
        (named explicitly in the proto), and the code we store on a meeting row
        is that same value.

        The window is filtered on ``start_time`` rather than ``end_time``: a
        conference is attributed to a scheduled meeting by when it STARTED
        relative to that meeting's slot, which is the rule the caller's
        3-hour affinity window encodes.

        Args:
            meeting_code (str): The Meet meeting code (e.g. "abc-defg-hij").
            start_time_after (str): ISO 8601 lower bound for the conference
                start time (inclusive).
            start_time_before (str): ISO 8601 upper bound for the conference
                start time (inclusive).

        Records for conferences that are still in progress are dropped here.
        ``list_ended_conferences`` filtered on ``end_time``, so an unfinished
        conference could never come back from it; filtering on ``start_time``
        means it can, and a live one has no ``endTime`` at all. Dropping it at
        this boundary keeps the "ended conferences only" guarantee callers
        already relied on -- the attendance sweep in particular parses
        ``end_time`` unconditionally, and selects meetings up to three hours
        ahead of now, so it meets live conferences routinely.

        Returns:
            list[dict]: ENDED conference records in the same shape
                ``list_ended_conferences`` returns -- name / space /
                start_time / end_time -- so both feed
                ``fetch_participants_for_record`` identically.
        """
        self.logger.debug(
            "[GoogleService] list_conferences_by_meeting_code: code=%s, after=%s, before=%s",
            meeting_code,
            start_time_after,
            start_time_before,
        )
        conferences = []
        request = meet_v2.ListConferenceRecordsRequest(
            filter=(
                f'space.meeting_code="{meeting_code}" '
                f'AND start_time>="{start_time_after}" '
                f'AND start_time<="{start_time_before}"'
            ),
        )
        pager = await self.meet_conference_records_client.list_conference_records(
            request=request
        )
        skipped_in_progress = 0
        async for record in pager:
            # No endTime means the conference is still running. Never emit it:
            # it would reach the caller as end_time="" and blow up the first
            # isoparse that touches it.
            if not record.end_time:
                skipped_in_progress += 1
                self.logger.debug(
                    "[GoogleService] list_conferences_by_meeting_code: code=%s, "
                    "skipping still-running record %s",
                    meeting_code,
                    record.name,
                )
                continue
            conferences.append({
                "name": record.name,
                "space": record.space,
                "start_time": record.start_time.isoformat()
                if record.start_time
                else "",
                "end_time": record.end_time.isoformat(),
            })
        self.logger.debug(
            "[GoogleService] list_conferences_by_meeting_code: code=%s fetched %d "
            "ended records, skipped %d still running",
            meeting_code,
            len(conferences),
            skipped_in_progress,
        )
        return conferences

    async def get_meeting_code_for_space(self, space_name: str) -> str:
        """
        Fetches the canonical meeting code for a Meet space.

        Args:
            space_name (str): The Meet space resource name (e.g., "spaces/abc-defg-hij").

        Returns:
            str: The human-readable meeting code (e.g., "abc-defg-hij").
        """
        self.logger.debug(
            "[GoogleService] get_meeting_code_for_space: space_name=%s", space_name
        )
        request = meet_v2.GetSpaceRequest(name=space_name)
        space = await self.meet_spaces_client.get_space(request=request)
        return space.meeting_code

    async def fetch_participants_for_record(self, record_name: str) -> list[dict]:
        """
        Fetches all participant sessions for a single conference record.

        Each entry captures the aggregated start/end time and identity
        (signed-in user or anonymous display name) for one person in the call.

        Args:
            record_name (str): The conference record resource name (e.g., "conferenceRecords/xxx").

        Returns:
            list[dict]: A list of participant entries, each containing:
                - start_time (str | None): Earliest join time in ISO 8601 format, or None.
                - end_time (str | None): Latest leave time in ISO 8601 format, or None.
                - signedin_user_id (str): Google user ID (present only for signed-in participants).
                - display_name (str): Display name of the participant.
        """
        self.logger.debug(
            "[GoogleService] fetch_participants_for_record: record_name=%s", record_name
        )
        result = []

        request = meet_v2.ListParticipantsRequest(parent=record_name)
        pager = await self.meet_conference_records_client.list_participants(
            request=request
        )

        async for participant in pager:
            item = {
                "start_time": (
                    participant.earliest_start_time.isoformat()
                    if participant.earliest_start_time
                    else None
                ),
                "end_time": (
                    participant.latest_end_time.isoformat()
                    if participant.latest_end_time
                    else None
                ),
            }

            if participant.signedin_user and participant.signedin_user.user:
                item["signedin_user_id"] = participant.signedin_user.user.split("/")[-1]
                item["display_name"] = participant.signedin_user.display_name

            if participant.anonymous_user:
                item["display_name"] = participant.anonymous_user.display_name

            result.append(item)

        self.logger.debug(
            "[GoogleService] fetch_participants_for_record: fetched %d participants",
            len(result),
        )
        return result

    def batch_delete_google_meetings(
        self,
        event_ids: list[str],
        calendar_id: str,
    ) -> tuple[list[str], list[str]]:
        """
        Delete one or more Google Calendar events in a single batch HTTP request.

        An event that is already absent from Calendar (404 / 410) counts as
        succeeded: deletion is about the end state, and the caller clears only
        the ids it is told succeeded. Reporting "already gone" as a failure
        would pin the row in ``mentorship_meeting`` permanently — a meeting
        the UI lists but can never remove, since every retry gets the same 404.

        Args:
            event_ids (list[str]): Google Calendar event IDs to delete.
            calendar_id (str): The calendar to delete from. Required and without
                a default: an id that does not exist on this calendar answers 404,
                which this method (correctly) counts as deleted -- so a wrong
                calendar here fails silently and is exactly the bug to avoid.

        Returns:
            tuple[list[str], list[str]]: Succeeded event IDs and failed event IDs.
        """
        if not event_ids:
            return [], []

        failed_event_ids: list[str] = []
        failed_id_set: set[str] = set()
        # Events the batch returned a definitive verdict for — deleted now, or
        # already gone. Tracked so a later batch-level error cannot retract a
        # verdict the batch already gave (see the except block below).
        resolved_event_ids: set[str] = set()

        def mark_failed(event_id):
            if event_id not in failed_id_set:
                failed_id_set.add(event_id)
                failed_event_ids.append(event_id)

        def handle_response(request_id, response, exception):
            if exception is None:
                resolved_event_ids.add(request_id)
                return

            status = getattr(getattr(exception, "resp", None), "status", None)
            if status in (HTTPStatus.NOT_FOUND, HTTPStatus.GONE):
                self.logger.info(
                    "[GoogleService] Batch delete: event_id=%s was already gone "
                    "(status=%s); counting it as deleted",
                    request_id,
                    status,
                )
                resolved_event_ids.add(request_id)
                return

            self.logger.error(
                "[GoogleService] Batch delete failed for event_id=%s: %s",
                request_id,
                exception,
            )
            mark_failed(request_id)

        for start in range(0, len(event_ids), BATCH_DELETE_SIZE):
            chunk = event_ids[start : start + BATCH_DELETE_SIZE]

            batch = self.google_calendar_client.new_batch_http_request(
                callback=handle_response
            )
            for event_id in chunk:
                batch.add(
                    self.google_calendar_client.events().delete(
                        calendarId=calendar_id,
                        eventId=event_id,
                        sendUpdates="all",
                    ),
                    request_id=event_id,
                )

            try:
                self.retry_utils.get_retry_on_transient(batch.execute)
            except Exception as e:
                self.logger.error(
                    "[GoogleService] Batch delete request failed for chunk=%s: %s",
                    chunk,
                    e,
                    exc_info=True,
                )
                # googleapiclient runs the callback as each sub-response is
                # parsed, so an error part-way through leaves earlier events
                # already deleted. Only the ones the batch never answered for
                # are genuinely unknown; failing the whole chunk would strand
                # the rest — gone from Calendar, still shown by Purrf.
                for event_id in chunk:
                    if event_id not in resolved_event_ids:
                        mark_failed(event_id)
                continue

        succeeded_event_ids = [
            event_id for event_id in event_ids if event_id not in failed_id_set
        ]

        return succeeded_event_ids, failed_event_ids
