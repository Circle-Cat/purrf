import json
import re
from datetime import datetime, timezone
from backend.common.constants import (
    GOOGLE_CALENDAR_LIST_INDEX_KEY,
    GOOGLE_CALENDAR_EVENT_DETAIL_KEY,
    GOOGLE_EVENT_ATTENDANCE_KEY,
    GOOGLE_CALENDAR_USER_EVENTS_KEY,
)
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
         - Only tracks attendance for meetings associated with Google accounts
           (i.e., participants with valid Google email addresses like `@circlecat.org`).
         - Meetings created by resources such as meeting rooms (without a Google account owner)
           will not have attendance records and are skipped.
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

    def _is_circlecat_email(self, email: str) -> bool:
        """
        Checks whether the given email address belongs to the circlecat.org domain.

        Args:
            email: The email address to validate.

        Returns:
            True if the email ends with '@circlecat.org', False otherwise.
        """
        return email.endswith("@circlecat.org")

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
            event_id = event.get("id", "unknown")
            self.logger.warning(
                "[GoogleCalendarSyncService] no valid Google Meet video entry found in the event: %s",
                event_id,
            )
            return None
        except Exception as e:
            self.logger.exception(f"Error extracting meeting code from event: {e}")
            return None

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

    def _get_calendars_events(
        self, calendar_ids: list[str], start_time: str, end_time: str
    ):
        """
        Fetch events for multiple calendars in a batched way, deduplicated by event_id.

        Args:
            calendar_ids: list of calendar IDs to fetch.
            start_time: RFC3339 start (inclusive).
            end_time: RFC3339 end (exclusive).

        Returns:
            dict: {
                event_id: {
                    "calendar_ids": list[str],
                    "summary": str,
                    "start": str,
                    "is_recurring": bool,
                    "meeting_code": str,
                }
            }
        """
        events_dict: dict[str, dict] = {}
        requests: list[tuple] = []

        def _enqueue_page(calendar_id: str, page_token: str | None = None):
            req = self.google_calendar_client.events().list(
                calendarId=calendar_id,
                timeMin=start_time,
                timeMax=end_time,
                singleEvents=True,
                orderBy="startTime",
                pageToken=page_token,
            )
            requests.append((req, calendar_id))

        for cid in calendar_ids:
            _enqueue_page(cid)

        def _callback(request_id, response, exception):
            calendar_id = request_id.split(":", 1)[0]
            if exception:
                self.logger.warning(
                    f"Batch request {request_id} for {calendar_id} failed: {exception}"
                )
                return

            page_events = response.get("items", [])
            if not page_events:
                return

            for event in page_events:
                event_id = event.get("id")
                summary = event.get("summary", "") or ""
                meeting_code = self._get_meeting_code_from_event(event)
                if not meeting_code:
                    continue

                start = event.get("start", {}).get("dateTime")
                if not start:
                    self.logger.debug(
                        f"Skipping event {event_id} from {calendar_id}: missing start"
                    )
                    continue

                is_recurring = "recurringEventId" in event

                if event_id in events_dict:
                    if not self._is_circlecat_email(calendar_id):
                        events_dict[event_id]["calendar_id"] = calendar_id
                else:
                    events_dict[event_id] = {
                        "calendar_id": calendar_id,
                        "summary": summary,
                        "start": start,
                        "is_recurring": is_recurring,
                        "meeting_code": meeting_code,
                    }

            next_token = response.get("nextPageToken")
            if next_token:
                try:
                    _enqueue_page(calendar_id, next_token)
                except Exception as e:
                    self.logger.warning(
                        f"Failed to enqueue next page for {calendar_id}: {e}"
                    )

        while requests:
            current_batch = []
            for _ in range(min(BATCH_SIZE, len(requests))):
                current_batch.append(requests.pop(0))

            batch = self.google_calendar_client.new_batch_http_request(
                callback=_callback
            )
            for req_obj, cid in current_batch:
                rid = f"{cid}:{uuid.uuid4()}"
                try:
                    batch.add(req_obj, request_id=rid)
                except Exception as e:
                    self.logger.warning(
                        f"Failed to add request for {cid} into batch: {e}"
                    )

            try:
                self.retry_utils.get_retry_on_transient(batch.execute)
            except Exception as e:
                self.logger.warning(f"Batch execution failed: {e}")

        return events_dict

    def _get_events_attendees(
        self, events: dict[str, dict], time_min: str = None, time_max: str = None
    ) -> dict[str, list]:
        """
        Fetch attendance for all events in bulk and return dict keyed by event_id,
        filtered by a time window if provided.

        Args:
            events: dict from _get_calendars_events(), keyed by event_id, each value containing:
                    - "calendar_id": str
                    - "summary": str
                    - "start": str
                    - "is_recurring": bool
                    - "meeting_code": str
            time_min: ISO 8601 start time (inclusive) to filter attendance.
            time_max: ISO 8601 end time (exclusive) to filter attendance.

        Returns:
            dict: { event_id: [ { "ldap": str, "join_time": str, "leave_time": str }, ... ] }
        """
        meeting_to_event = {
            e_data["meeting_code"]: event_id
            for event_id, e_data in events.items()
            if e_data.get("meeting_code")
        }

        if not meeting_to_event:
            return {}

        results: dict[str, list] = {
            event_id: [] for event_id in meeting_to_event.values()
        }
        meeting_codes = list(meeting_to_event.keys())

        def _callback(request_id, response, exception):
            code = request_id
            event_id = meeting_to_event.get(code)
            if not event_id:
                return

            if exception:
                self.logger.warning(
                    f"Failed to fetch attendance for meeting {code}: {exception}"
                )
                results[event_id] = []
                return

            activities = response.get("items", [])
            attendance_list = []

            for activity in activities:
                for event in activity.get("events", []):
                    params = {
                        p.get("name"): p.get("value") or p.get("intValue")
                        for p in event.get("parameters", [])
                    }

                    email = event.get("actor", {}).get("email") or params.get(
                        "identifier"
                    )
                    if not email or not self._is_circlecat_email(email):
                        continue

                    ldap = email.split("@")[0]
                    start_ts = int(params.get("start_timestamp_seconds"))
                    duration = int(params.get("duration_seconds", 0))
                    join_time_ts = start_ts
                    leave_time_ts = start_ts + duration

                    join_date = datetime.utcfromtimestamp(join_time_ts).date()
                    join_time = (
                        datetime.fromtimestamp(join_time_ts, tz=timezone.utc)
                        .isoformat()
                        .replace("+00:00", "Z")
                    )
                    leave_time = (
                        datetime.fromtimestamp(leave_time_ts, tz=timezone.utc)
                        .isoformat()
                        .replace("+00:00", "Z")
                    )

                    if events[event_id].get("is_recurring"):
                        try:
                            recurrence_suffix = event_id.split("_")[-1]
                            recurrence_instance_date = datetime.strptime(
                                recurrence_suffix, "%Y%m%dT%H%M%SZ"
                            ).date()
                        except Exception as e:
                            self.logger.warning(
                                f"Failed to parse recurrence date for {event_id}: {e}"
                            )
                        if (
                            recurrence_instance_date
                            and join_date != recurrence_instance_date
                        ):
                            continue

                    attendance_list.append({
                        "ldap": ldap,
                        "join_time": join_time,
                        "leave_time": leave_time,
                    })

            results[event_id] = attendance_list

        for i in range(0, len(meeting_codes), BATCH_SIZE):
            chunk = meeting_codes[i : i + BATCH_SIZE]
            batch = self.google_reports_client.new_batch_http_request(
                callback=_callback
            )

            for code in chunk:
                req = self.google_reports_client.activities().list(
                    userKey="all",
                    applicationName="meet",
                    eventName="call_ended",
                    filters=f"meeting_code=={code}",
                    maxResults=1000,
                )
                batch.add(req, request_id=code)

            self.retry_utils.get_retry_on_transient(batch.execute)
            time.sleep(SLEEP_BETWEEN_BATCHES)

        return results

    def _cache_calendars(self) -> list[str]:
        """
        Fetches calendar metadata from the Google Calendar API, filters out irrelevant calendars,
        caches the valid calendar metadata into Redis, and inserts a static entry:
        'personal' → 'Personal Calendars'.

        Returns:
            List of cached calendar IDs (excluding "personal").

        Raises:
            Any exception raised by `get_calendar_list` or Redis operations will be retried up to 3 times.
        """
        calendar_list = self._get_calendar_list()

        filtered_calendar_list = []

        for calendar in calendar_list:
            calendar_id = calendar.get("calendar_id", "")
            if self._is_circlecat_email(calendar_id):  # Skip personal user calendars
                continue
            elif calendar_id.endswith(
                "@group.v.calendar.google.com"
            ):  # Skip system-generated calendars
                continue
            filtered_calendar_list.append(calendar)

        pipeline = self.redis_client.pipeline()
        pipeline.hset(GOOGLE_CALENDAR_LIST_INDEX_KEY, "personal", "Personal Calendars")

        cached_calendar_ids = []

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
            cached_calendar_ids.append(calendar_id)

        self.retry_utils.get_retry_on_transient(pipeline.execute)

        return cached_calendar_ids

    def _cache_calendar_events(
        self, calendar_ids: list[str], time_min: str, time_max: str
    ) -> dict[str, dict]:
        """
        Fetch events for multiple calendars, cache event details (summary, calendar_id alias, is_recurring),
        and return events dictionary.

        Args:
            calendar_ids: List of calendar IDs.
            time_min: ISO 8601 start time (inclusive).
            time_max: ISO 8601 end time (exclusive).

        Returns:
            dict: { event_id: event_dict } for all fetched events.
                Each event_dict contains:
                - calendar_id: str
                - summary: str
                - start: str
                - is_recurring: bool
                - meeting_code: str
        """
        events_dict = {}
        pipeline = self.redis_client.pipeline()

        all_events = self._get_calendars_events(calendar_ids, time_min, time_max)

        for event_id, event in all_events.items():
            try:
                self.json_schema_validator.validate_data(
                    event, "calendar_event.schema.json"
                )
            except Exception as e:
                self.logger.warning(f"Invalid event skipped: {e}")
                continue

            base_event_id = event_id.split("_")[0]

            calendar_id = event.get("calendar_id", "")
            if self._is_circlecat_email(calendar_id):
                calendar_alias = "personal"
            else:
                calendar_alias = calendar_id

            pipeline.set(
                GOOGLE_CALENDAR_EVENT_DETAIL_KEY.format(event_id=base_event_id),
                json.dumps({
                    "summary": event.get("summary", ""),
                    "calendar_id": calendar_alias,
                    "is_recurring": event.get("is_recurring", False),
                }),
            )

            events_dict[event_id] = event

        self.retry_utils.get_retry_on_transient(pipeline.execute)

        return events_dict

    def _cache_events_attendees(
        self, events: dict[str, dict], time_min: str, time_max: str
    ):
        """
        Fetch and cache attendance data for a batch of events.

        Args:
            events: Dictionary of events keyed by event_id. Each event dict should include:
                    - calendar_id: str
                    - meeting_code
                    - start
                    - is_recurring
        """
        if not events:
            return

        attendance_map = self._get_events_attendees(events, time_min, time_max)

        pipeline = self.redis_client.pipeline()

        for event_id, event in events.items():
            attendees = attendance_map.get(event_id, [])
            calendar_id = event.get("calendar_id", "")

            try:
                score = int(datetime.fromisoformat(event["start"]).timestamp())
            except Exception as e:
                self.logger.warning(f"Invalid start time for event {event_id}: {e}")
                continue

            for attendee in attendees:
                ldap = attendee.get("ldap")
                if not ldap:
                    continue

                record_str = json.dumps({
                    "join_time": attendee.get("join_time"),
                    "leave_time": attendee.get("leave_time"),
                })

                attendance_key = GOOGLE_EVENT_ATTENDANCE_KEY.format(
                    event_id=event_id, ldap=ldap
                )
                pipeline.sadd(attendance_key, record_str)

                calendar_alias = (
                    "personal" if self._is_circlecat_email(calendar_id) else calendar_id
                )
                pipeline.zadd(
                    GOOGLE_CALENDAR_USER_EVENTS_KEY.format(
                        calendar_id=calendar_alias, ldap=ldap
                    ),
                    {event_id: score},
                )

        self.retry_utils.get_retry_on_transient(pipeline.execute)

    def pull_calendar_history(self, time_min: str = None, time_max: str = None):
        """
        Pulls and caches historical calendar event data for all calendars.

        Args:
            time_min (str): ISO 8601 start time (inclusive).
            time_max (str): ISO 8601 end time (exclusive).
        """
        calendar_ids = self._cache_calendars()

        ldaps = self.google_service.list_directory_all_people_ldap().values()
        personal_calendar_ids = [f"{ldap}@circlecat.org" for ldap in ldaps]
        all_calendar_ids = calendar_ids + personal_calendar_ids

        events_dict = self._cache_calendar_events(all_calendar_ids, time_min, time_max)

        self._cache_events_attendees(events_dict, time_min, time_max)
