import json
import re
from datetime import datetime
from backend.common.constants import (
    GOOGLE_CALENDAR_LIST_INDEX_KEY,
    GOOGLE_CALENDAR_EVENT_DETAIL_KEY,
    GOOGLE_EVENT_ATTENDANCE_KEY,
    GOOGLE_CALENDAR_USER_EVENTS_KEY,
)


class GoogleCalendarSyncService:
    def __init__(
        self,
        logger,
        redis_client,
        google_calendar_client,
        google_reports_client,
        retry_utils,
        json_schema_validator,
        google_service,
    ):
        """
        Initializes the GoogleCalendarSyncService with necessary clients and logger.

        Args:
            logger: The logger instance for logging messages.
            redis_client: The Redis client instance.
            google_calendar_client: The GoogleClient factory instance.
            retry_utils: A RetryUtils for handling retries on transient errors.
            json_schema_validator: A JsonSchemaValidator instance.
            google_service: The Google Service instance.
        """
        self.logger = logger
        self.redis_client = redis_client
        self.google_calendar_client = google_calendar_client
        self.google_reports_client = google_reports_client
        self.retry_utils = retry_utils
        self.json_schema_validator = json_schema_validator
        self.google_service = google_service

    def _get_calendar_list(self):
        """
        Fetches the list of calendars accessible using the Google Calendar API.

        Returns:
            A list of calendar dictionaries, each with:
                - calendar_id
                - summary
            Returns an empty list if an error occurs or no calendars are found.
        """
        try:
            calendars = []

            def _fetch_page(page_token=None):
                return (
                    self.google_calendar_client.calendarList()
                    .list(pageToken=page_token)
                    .execute()
                )

            page_token = None
            while True:
                response = self.retry_utils.get_retry_on_transient(
                    lambda: _fetch_page(page_token)
                )
                items = response.get("items", [])
                for item in items:
                    calendars.append({
                        "calendar_id": item.get("id"),
                        "summary": item.get("summary"),
                    })
                page_token = response.get("nextPageToken")
                if not page_token:
                    break

            return calendars

        except Exception as e:
            self.logger.error("Unexpected error fetching calendars", e)
            return []

    def _get_calendar_events(self, calendar_id: str, start_time: str, end_time: str):
        """
        Fetches events for a given calendar ID and time range using the Google Calendar API.

        Args:
            calendar_id: The specific calendar's ID (e.g., 'primary' or a shared calendar ID).
            start_time: RFC3339 timestamp for the start of the range (inclusive).
            end_time: RFC3339 timestamp for the end of the range (exclusive).

        Returns:
            A list of events (dictionaries) from the calendar.
        """
        events = []
        page_token = None

        def _fetch_page(page_token=None):
            return (
                self.google_calendar_client.events()
                .list(
                    calendarId=calendar_id,
                    timeMin=start_time,
                    timeMax=end_time,
                    singleEvents=True,
                    orderBy="startTime",
                    pageToken=page_token,
                )
                .execute()
            )

        while True:
            events_result = self.retry_utils.get_retry_on_transient(
                lambda: _fetch_page(page_token)
            )

            for event in events_result.get("items", []):
                event_id = event.get("id")
                summary = event.get("summary", "")
                start = event.get("start", {}).get("dateTime")
                attendance_data = None
                is_recurring = "recurringEventId" in event

                meet_code = self._get_meeting_code_from_event(event)
                if meet_code:
                    try:
                        attendance_data = self._get_event_attendance(
                            meet_code, is_recurring, event_id
                        )
                    except Exception as e:
                        self.logger.warning(
                            f"Failed to fetch attendance for event {event_id}: {e}"
                        )

                events.append({
                    "event_id": event_id,
                    "calendar_id": calendar_id,
                    "summary": summary or "",
                    "start": start or "",
                    "attendees": attendance_data or [],
                    "is_recurring": is_recurring,
                })

            page_token = events_result.get("nextPageToken")
            if not page_token:
                break

        return events

    def _is_circlecat_email(self, email: str) -> bool:
        """
        Checks whether the given email address belongs to the circlecat.org domain.

        Args:
            email: The email address to validate.

        Returns:
            True if the email ends with '@circlecat.org', False otherwise.
        """
        return email.endswith("@circlecat.org")

    def _get_event_attendance(
        self, meeting_code: str, is_recurring: bool = False, event_id: str = None
    ):
        """
        Fetches actual Google Meet attendance (participants) for a calendar event using the Reports API.

        Args:
            meeting_code: The unique code for the Google Meet session.
            is_recurring: Whether the event is part of a recurring series.
            event_id: The full event ID (e.g., 4gnl5pmrltdb8so1e273gmgqp0_20250702T013000Z)
            is_recurring: Whether the event is part of a recurring series.
            event_id: The full event ID (e.g., 4gnl5pmrltdb8so1e273gmgqp0_20250702T013000Z)

        Returns:
            A list of dictionaries containing participant details: email, duration, join/leave times.
        """
        attendance_details = []
        next_page_token = None

        def _fetch_page(page_token=None):
            return (
                self.google_reports_client.activities()
                .list(
                    userKey="all",
                    applicationName="meet",
                    eventName="call_ended",
                    filters=f"meeting_code=={meeting_code}",
                    maxResults=1000,
                    pageToken=page_token,
                )
                .execute()
            )

        recurrence_instance_date = None
        if is_recurring and event_id:
            try:
                recurrence_suffix = event_id.split("_")[
                    -1
                ]  # e.g., '20250702T013000Z' → '2025-07-02'
                recurrence_instance_date = datetime.strptime(
                    recurrence_suffix, "%Y%m%dT%H%M%SZ"
                ).date()
            except Exception as e:
                self.logger.warning(
                    f"Failed to parse recurrence date from event_id: {event_id}: {e}"
                )

        while True:
            response = self.retry_utils.get_retry_on_transient(
                lambda: _fetch_page(next_page_token)
            )

            activities = response.get("items", [])
            if not activities:
                self.logger.warning(
                    f"No attendance data found for meeting code: {meeting_code}"
                )
                break

            for activity in activities:
                events = activity.get("events", [])

                for event in events:
                    parameters = event.get("parameters", [])
                    data = {}

                    for param in parameters:
                        key = param.get("name")
                        if "intValue" in param:
                            data[key] = int(
                                param["intValue"]
                            )  # "intValue" is used for numeric fields (e.g., duration, timestamps)
                        elif "value" in param:
                            data[key] = param[
                                "value"
                            ]  # "value" is used for string fields (e.g., user identifier, device info)

                    email = event.get("actor", {}).get("email") or data.get(
                        "identifier"
                    )

                    duration_seconds = data.get("duration_seconds", 0)
                    start_ts = data.get("start_timestamp_seconds")

                    join_time = (
                        datetime.utcfromtimestamp(start_ts).isoformat()
                        if start_ts
                        else None
                    )
                    leave_time = (
                        datetime.utcfromtimestamp(
                            start_ts + duration_seconds
                        ).isoformat()
                        if start_ts and duration_seconds
                        else None
                    )

                    if recurrence_instance_date and join_time:
                        join_date = datetime.fromisoformat(join_time).date()
                        if join_date != recurrence_instance_date:
                            continue
                    if email and self._is_circlecat_email(email):
                        attendance_details.append({
                            "email": email,
                            "duration_seconds": duration_seconds,
                            "join_time": join_time,
                            "leave_time": leave_time,
                        })

            next_page_token = response.get("nextPageToken")
            if not next_page_token:
                break

        self.logger.info(
            f"Fetched {len(attendance_details)} attendance records for meeting code: {meeting_code}"
        )
        return attendance_details

    def _get_meeting_code_from_event(self, event):
        """
        Extracts the Google Meet meeting code from a Google Calendar event.

        Args:
            event (dict): A Google Calendar event resource.

        Returns:
            str or None: The meeting code, or None if not found.
        """
        try:
            entry_points = event.get("conferenceData", {}).get("entryPoints", [])
            for entry in entry_points:
                if entry.get("entryPointType") == "video" and "uri" in entry:
                    uri = entry["uri"]
                    match = re.search(
                        r"https?://meet\.google\.com/([a-z]+)(?:-([a-z]+))?(?:-([a-z]+))?",
                        uri,
                    )
                    if match:
                        groups = match.groups()
                        meeting_code = "".join(filter(None, groups))
                        self.logger.info(
                            f"Extracted meeting code: {meeting_code} from URI: {uri}"
                        )
                        return meeting_code
            self.logger.warning("No valid Google Meet video entry found in the event.")
            return None
        except Exception as e:
            self.logger.exception(f"Error extracting meeting code from event: {e}")
            return None

    def _cache_calendars(self):
        """
        Fetches calendar metadata from the Google Calendar API, filters out irrelevant calendars,
        and caches the valid calendar metadata into Redis. Also inserts a static entry: 'personal' → 'Personal Calendars'.

        Raises:
            Any exception raised by `get_calendar_list` or Redis operations will be retried up to 3 times with exponential backoff.
        """
        calendar_list = self._get_calendar_list()

        filtered_calendar_list = []
        ldap = None

        for calendar in calendar_list:
            calendar_id = calendar.get("calendar_id", "")
            if self._is_circlecat_email(calendar_id):  # Skip personal user calendars
                ldap = calendar_id.split("@")[0]
                continue
            elif calendar_id.endswith(
                "@group.v.calendar.google.com"
            ):  # Skip system-generated Google group calendars
                continue
            filtered_calendar_list.append(calendar)

        if ldap is None:
            self.logger.warning(
                "No calendar_id ending with @circlecat.org found; skipping caching."
            )
            return

        pipeline = self.redis_client.pipeline()
        pipeline.hset(GOOGLE_CALENDAR_LIST_INDEX_KEY, "personal", "Personal Calendars")

        for calendar in filtered_calendar_list:
            try:
                self.json_schema_validator.validate_data(
                    calendar, "calendar.schema.json"
                )
            except Exception as e:
                self.logger.warning(f"Invalid calendar skipped: {e}")
                continue

            calendar_id = calendar["calendar_id"]
            pipeline.hset(
                GOOGLE_CALENDAR_LIST_INDEX_KEY, calendar_id, calendar["summary"]
            )
            self.logger.debug(f"Cached calendar {calendar_id} for purrf")

        self.retry_utils.get_retry_on_transient(pipeline.execute)

    def cache_events(
        self, calendar_id: str, time_min: str, time_max: str, skip_event_ids: set = None
    ):
        """
        Fetches calendar events from the Google Calendar API and caches structured event and
        attendance data in Redis for later retrieval and analytics.

        The function performs the following tasks:
        - Identifies the calendar alias (e.g., "personal") for display purposes based on the email domain.
        - Retrieves events from the specified calendar within the given time range.
        - Skips any events that have already been processed (if `skip_event_ids` is provided).
        - Stores key event metadata (summary, calendar ID alias, recurrence flag) in Redis.

        Args:
            calendar_id (str): The Google calendar ID.
            time_min (str): ISO 8601 start time (inclusive).
            time_max (str): ISO 8601 end time (exclusive).
            skip_event_ids (set): Optional set to avoid duplicate event processing.

        Returns:
            set: Updated set of processed event IDs.
        """
        skip_event_ids = skip_event_ids or set()
        calendar_id_alias = (
            "personal" if self._is_circlecat_email(calendar_id) else calendar_id
        )

        pipeline = self.redis_client.pipeline()

        events = self._get_calendar_events(calendar_id, time_min, time_max)

        for event in events:
            event_id = event["event_id"]
            if event_id in skip_event_ids:
                continue

            skip_event_ids.add(event_id)

            try:
                self.json_schema_validator.validate_data(
                    event, "calendar_event.schema.json"
                )
            except Exception as e:
                self.logger.warning(f"Invalid event skipped: {e}")
                continue

            base_event_id = event_id.split("_")[0]
            pipeline.set(
                GOOGLE_CALENDAR_EVENT_DETAIL_KEY.format(event_id=base_event_id),
                json.dumps({
                    "summary": event.get("summary", ""),
                    "calendar_id": calendar_id_alias,
                    "is_recurring": event.get("is_recurring", False),
                }),
            )

            try:
                score = int(datetime.fromisoformat(event["start"]).timestamp())
            except Exception as e:
                self.logger.warning(f"Invalid start time for event {event_id}: {e}")
                continue

            for attendee in event.get("attendees", []):
                attendee_ldap = attendee.get("email").split("@")[0]
                if not attendee_ldap:
                    continue

                attendance_key = GOOGLE_EVENT_ATTENDANCE_KEY.format(
                    event_id=event_id, ldap=attendee_ldap
                )
                record_str = json.dumps({
                    "join_time": attendee["join_time"],
                    "leave_time": attendee["leave_time"],
                })

                pipeline.zadd(
                    GOOGLE_CALENDAR_USER_EVENTS_KEY.format(
                        calendar_id=calendar_id_alias, ldap=attendee_ldap
                    ),
                    {event_id: score},
                )
                pipeline.sadd(attendance_key, record_str)

        self.retry_utils.get_retry_on_transient(pipeline.execute)

        return skip_event_ids

    def pull_calendar_history(self, time_min: str = None, time_max: str = None):
        """
        Pulls and caches historical calendar event data for all calendars.

        Args:
            time_min (str): The ISO 8601 start time (inclusive) for fetching calendar events.
            time_max (str): The ISO 8601 end time (exclusive) for fetching calendar events.

        Raises:
            RuntimeError: If a Redis client cannot be obtained.
            Any exception raised by `cache_calendars()` or `cache_events()` will be retried up to 3 times using exponential backoff due to the `@retry` decorator.
        """
        self._cache_calendars()
        calendar_ids = self.redis_client.hkeys(GOOGLE_CALENDAR_LIST_INDEX_KEY)

        processed_event_ids = set()

        for calendar_id in calendar_ids:
            if calendar_id == "personal":
                continue
            processed_event_ids |= self.cache_events(calendar_id, time_min, time_max)

        ldaps = self.google_service.list_directory_all_people_ldap().values()
        personal_calendar_ids = [f"{ldap}@circlecat.org" for ldap in ldaps]

        for personal_calendar_id in personal_calendar_ids:
            processed_event_ids |= self.cache_events(
                personal_calendar_id, time_min, time_max, processed_event_ids
            )
