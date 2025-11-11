import json
import re
from datetime import datetime
from backend.common.constants import (
    GOOGLE_CALENDAR_LIST_INDEX_KEY,
    GOOGLE_CALENDAR_EVENT_DETAIL_KEY,
    GOOGLE_EVENT_ATTENDANCE_KEY,
    GOOGLE_CALENDAR_USER_EVENTS_KEY,
)
from collections import defaultdict
import uuid
import time

# Google Reports API rate limits:
# - Batch requests can include at most 10 calls.
# - With filters, the API allows ~250 requests per minute.
#
# Using 10 requests per batch + a 2.5s delay keeps us safely under the limit.
BATCH_SIZE = 10
SLEEP_BETWEEN_BATCHES = 2.5


class GoogleCalendarSyncService:
    """
    A service responsible for synchronizing Google Calendar and Google Meet attendance data
    into Redis for efficient querying and analytics.

    This service handles:
      - Fetching and caching calendar metadata.
      - Retrieving and validating Google Calendar events.
      - Extracting Google Meet meeting codes and attendance data.
      - Caching structured event and attendance data in Redis for later processing.

    Core functionalities:
      1. **Calendar Management**:
         - Fetches all accessible calendars using the Google Calendar API.
         - Filters out irrelevant or system-generated calendars.
         - Caches valid calendar metadata (ID → summary) into Redis.

      2. **Event Retrieval and Caching**:
         - Fetches events within a specific time range for each calendar.
         - Handles pagination using Google Calendar batch requests.
         - Extracts event details and associated Google Meet attendance.
         - Validates data schemas before caching to ensure data consistency.

      3. **Attendance Tracking**:
         - Retrieves Google Meet attendance reports via the Google Reports API.
         - Supports batched attendance queries for multiple meeting codes.
         - Filters attendance to include only organization-specific participants
           (e.g., users with `@circlecat.org` emails).
         - Associates attendance records with calendar events in Redis.
    """

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
        Fetch all Google Calendar events within a given time range, with batched
        pagination and bulk attendance lookup.

        This method issues Google Calendar API `events.list` requests using the
        batch API so that multiple pages can be fetched efficiently. Each page of
        events is processed in the batch callback, where the method extracts Google
        Meet meeting codes, resolves recurrence information, and calls
        `_get_bulk_event_attendance()` to fetch attendance data for all meetings
        in that page in a single batched Reports API request.

        Args:
            calendar_id: The specific calendar's ID (e.g., 'primary' or a shared calendar ID).
            start_time: RFC3339 timestamp for the start of the range (inclusive).
            end_time: RFC3339 timestamp for the end of the range (exclusive).

        Returns:
            A list of events (dictionaries) from the calendar.
        """
        events = []
        requests = []

        def _callback(request_id, response, exception):
            if exception:
                self.logger.warning(f"Batch request {request_id} failed: {exception}")
                return

            page_events = response.get("items", [])
            if not page_events:
                return

            meeting_codes = []
            event_id_map = {}
            recurring_map = {}

            for event in page_events:
                meet_code = self._get_meeting_code_from_event(event)
                if meet_code:
                    meeting_codes.append(meet_code)
                    event_id_map[meet_code] = event.get("id")
                    recurring_map[meet_code] = "recurringEventId" in event

            bulk_attendance = self._get_bulk_event_attendance(
                meeting_codes, event_id_map, recurring_map
            )

            for event in page_events:
                event_id = event.get("id")
                summary = event.get("summary", "")
                start = event.get("start", {}).get("dateTime")
                if not start:
                    self.logger.warning(
                        f"Skipping event {event_id} because it has no valid start time."
                    )
                    continue
                is_recurring = "recurringEventId" in event
                meet_code = self._get_meeting_code_from_event(event)

                events.append({
                    "event_id": event_id,
                    "calendar_id": calendar_id,
                    "summary": summary or "",
                    "start": start or "",
                    "attendees": bulk_attendance.get(meet_code, []),
                    "is_recurring": is_recurring,
                })

            next_token = response.get("nextPageToken")
            if next_token:
                requests.append(
                    self.google_calendar_client.events().list(
                        calendarId=calendar_id,
                        timeMin=start_time,
                        timeMax=end_time,
                        singleEvents=True,
                        orderBy="startTime",
                        pageToken=next_token,
                    )
                )

        requests.append(
            self.google_calendar_client.events().list(
                calendarId=calendar_id,
                timeMin=start_time,
                timeMax=end_time,
                singleEvents=True,
                orderBy="startTime",
            )
        )

        while requests:
            current_requests = list(requests)
            requests.clear()

            batch = self.google_calendar_client.new_batch_http_request(
                callback=_callback
            )
            for req in current_requests:
                req_id = getattr(req, "request_id", None) or req.uri
                batch.add(req, request_id=req_id)

            self.retry_utils.get_retry_on_transient(batch.execute)

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

    def _get_bulk_event_attendance(
        self,
        meeting_codes: list[str],
        event_id_map: dict[str, str],
        recurring_map: dict[str, bool],
    ):
        """
        Fetch attendance records for multiple Google Meet meeting codes in parallel
        using Google Admin Reports API batch requests.

        The Reports API returns activity records for `call_ended` events that
        include participant join/leave timestamps, identifiers, and duration
        metadata. This method batches up to `BATCH_SIZE` meeting-code queries into
        a single HTTP batch to reduce latency and API quota usage.

        Args:
            meeting_codes: List of Google Meet codes.
            event_id_map: Mapping meeting_code -> full event_id (used for recurring events).
            recurring_map: Mapping meeting_code -> bool, whether event is recurring.

        Returns:
            dict: meeting_code -> list of attendance records
        """
        results = defaultdict(list)

        def _callback(request_id, response, exception):
            code = request_id.split("_")[0]
            if exception:
                self.logger.warning(
                    f"Failed to fetch attendance for meeting {code}: {exception}"
                )
                return

            recurrence_instance_date = None
            event_id = event_id_map.get(code)
            is_recurring = recurring_map.get(code, False)

            if is_recurring and event_id:
                try:
                    recurrence_suffix = event_id.split("_")[
                        -1
                    ]  # e.g., 20250702T013000Z
                    recurrence_instance_date = datetime.strptime(
                        recurrence_suffix, "%Y%m%dT%H%M%SZ"
                    ).date()
                except Exception as e:
                    self.logger.warning(
                        f"Failed to parse recurrence date for {event_id}: {e}"
                    )

            activities = response.get("items", [])
            for activity in activities:
                for event in activity.get("events", []):
                    parameters = event.get("parameters", [])
                    data = {}

                    for param in parameters:
                        key = param.get("name")
                        if "intValue" in param:
                            data[key] = int(param["intValue"])
                        elif "value" in param:
                            data[key] = param["value"]

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
                        results[code].append({
                            "email": email,
                            "duration_seconds": duration_seconds,
                            "join_time": join_time,
                            "leave_time": leave_time,
                        })

        for i in range(0, len(meeting_codes), BATCH_SIZE):
            batch_codes = [c for c in meeting_codes[i : i + BATCH_SIZE] if c]
            batch = self.google_reports_client.new_batch_http_request(
                callback=_callback
            )

            for code in batch_codes:
                req = self.google_reports_client.activities().list(
                    userKey="all",
                    applicationName="meet",
                    eventName="call_ended",
                    filters=f"meeting_code=={code}",
                    maxResults=1000,
                )
                batch.add(req, request_id=f"{code}_{uuid.uuid4()}")

            self.retry_utils.get_retry_on_transient(batch.execute)
            time.sleep(SLEEP_BETWEEN_BATCHES)

        return results

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

        # TODO: [PUR-258] Currently, each batch processes events for a single user.
        # However, not every user has enough events to fill the BATCH_SIZE (10).
        # We could optimize by grouping multiple users' event requests together
        # into batches of up to 10 requests to better utilize batch parallelism
        # and reduce overall API latency.

        for personal_calendar_id in personal_calendar_ids:
            processed_event_ids |= self.cache_events(
                personal_calendar_id, time_min, time_max, processed_event_ids
            )
