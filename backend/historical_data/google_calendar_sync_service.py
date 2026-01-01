import json
import re
import uuid
import time
from datetime import datetime, timezone

from backend.common.constants import (
    GOOGLE_CALENDAR_LIST_INDEX_KEY,
    GOOGLE_CALENDAR_EVENT_DETAIL_KEY,
    GOOGLE_EVENT_ATTENDANCE_KEY,
    GOOGLE_CALENDAR_USER_EVENTS_KEY,
)
from backend.dto.calendar_dto import CalendarDTO, AttendanceDTO, CalendarEventDTO

# Google Reports API rate limits:
# - Batch requests can include at most 10 calls.
# - With filters, the API allows ~250 requests per minute.
#
# Using 10 requests per batch + a 2.5s delay keeps us safely under the limit.
BATCH_SIZE = 10
SLEEP_BETWEEN_BATCHES = 2.5
# Define the matching window: the join time must be within ±2 hours of the scheduled start time
MATCH_WINDOW_SECONDS = 7200


class GoogleCalendarSyncService:
    """
    Synchronizes Google Calendar events and Google Meet attendance data into Redis
    for efficient querying, analytics, and downstream processing.

    This service integrates multiple Google Workspace APIs and is responsible for:
      - Discovering and caching accessible calendars.
      - Fetching calendar events within a given time range.
      - Extracting Google Meet meeting codes from calendar events.
      - Retrieving Google Meet attendance (join/leave) records via Admin Reports API.
      - Normalizing and caching event and attendance data into Redis.

    --------------------
    IMPORTANT LIMITATIONS
    --------------------
    Google Meet attendance data is retrieved from the Google Admin Reports API
    (`applications=meet`, `eventName=call_ended`), which has a strict data retention
    policy:

      - Only the last **180 days** of audit logs are available.
      - Attendance data older than 180 days is **permanently unrecoverable**.
      - Providing a wider time range will result in API errors unless clamped.

    As a result:
      - This service can only synchronize Meet attendance within the most recent
        180-day window.
      - Long-term or historical attendance data must be cached proactively by this
        service if it is required for future analysis.

    --------------------
    DESIGN NOTES
    --------------------
    - A single Google Meet meeting code may correspond to multiple calendar event
      instances (e.g. recurring meetings). Attendance records are matched to the
      correct event instance based on proximity between the actual join time and
      the scheduled event start time.
    - Only participants with valid Google Workspace user emails
      (e.g. `@circlecat.org`) are tracked.
    - Meetings created by resources (e.g. meeting rooms or devices without a user
      account) do not produce attendance logs and are skipped.
    - Third-party conference providers (e.g. Microsoft Teams) are explicitly
      detected and excluded.

    --------------------
    DATA STORED IN REDIS
    --------------------
    - Calendar metadata (calendar_id → summary)
    - Event metadata (summary, calendar_id, recurrence flag)
    - Attendance records (per event, per user)
    - User-to-event indices for efficient lookup

    This class is designed to be idempotent, resilient to transient API failures,
    and safe to run repeatedly within the supported time window.
    """

    def __init__(
        self,
        logger,
        redis_client,
        google_calendar_client,
        google_reports_client,
        retry_utils,
        google_service,
    ):
        """
        Initializes the GoogleCalendarSyncService with necessary clients and logger.

        Args:
            logger: The logger instance for logging messages.
            redis_client: The Redis client instance.
            google_calendar_client: The GoogleClient factory instance.
            retry_utils: A RetryUtils for handling retries on transient errors.
            google_service: The Google Service instance.
        """
        self.logger = logger
        self.redis_client = redis_client
        self.google_calendar_client = google_calendar_client
        self.google_reports_client = google_reports_client
        self.retry_utils = retry_utils
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

    def _detect_third_party_conference(self, event: dict) -> str | None:
        """
        Detect third-party conference providers from a Google Calendar event.

        Design note:
            Currently, only Microsoft Teams is supported, which is the only
            third-party meeting type observed so far.

        TODO:
            When additional third-party conference providers (e.g. Zoom, Webex,
            Lark) are introduced, refactor the return value into an enum-based
            conference type instead of plain strings.

        Returns:
            str | None: provider name (e.g. 'microsoft_teams'),
                        or None if not detected.
        """
        text = " ".join(
            filter(
                None,
                [
                    event.get("location", ""),
                    event.get("description", ""),
                ],
            )
        ).lower()

        if "microsoft teams" in text:
            return "microsoft_teams"
        return None

    def _get_meeting_code_from_event(self, event: dict) -> str | None:
        """
        Extracts the Google Meet meeting code from a Google Calendar event.

        This method attempts to retrieve the Google Meet meeting code from the
        event's `conferenceData.entryPoints`. If the event is detected as a
        third-party conference (e.g. Microsoft Teams), it will be explicitly
        skipped and return None.

        Args:
            event (dict): A Google Calendar event resource.

        Returns:
            str | None:
                - The normalized Google Meet meeting code (hyphens removed),
                if a valid Google Meet video entry is found.
                - None if the event does not contain a Google Meet link or is a
                supported third-party conference.
        """
        try:
            entry_points = event.get("conferenceData", {}).get("entryPoints", [])
            for entry in entry_points:
                if entry.get("entryPointType") == "video" and "uri" in entry:
                    uri = entry["uri"]
                    match = re.search(r"meet\.google\.com/([a-z-]+)", uri)
                    if match:
                        meeting_code = match.group(1).replace("-", "")
                        self.logger.debug(
                            "[GoogleCalendarSyncService] extracted meeting code %s from URI %s",
                            meeting_code,
                            uri,
                        )
                        return meeting_code

            meeting_source = self._detect_third_party_conference(event)
            if meeting_source:
                self.logger.info(
                    "[GoogleCalendarSyncService] skipping third-party meeting provider=%s, summary=%s",
                    meeting_source,
                    event.get("summary", ""),
                )
                return None

            event_id = event.get("id", "unknown")
            self.logger.warning(
                "[GoogleCalendarSyncService] no valid Google Meet video entry found in event_id=%s",
                event_id,
            )
            return None

        except Exception as e:
            self.logger.exception(
                "[GoogleCalendarSyncService] error extracting meeting code from calendar event: %s",
                e,
            )
            return None

    def _get_calendar_list(self) -> list[CalendarDTO]:
        """
        Retrieve all calendars accessible to the current Google account.

        This method queries the Google Calendar API and returns a list of
        calendars that the authenticated user has access to. Pagination is
        handled internally until all calendar entries are fetched.

        In case of any unexpected error (API failure, permission issue, etc.),
        the method logs the error and returns an empty list instead of raising
        an exception, allowing the synchronization process to continue safely.

        Returns:
            list[CalendarDTO]:
                A list of CalendarDTO objects containing:
                - calendar_id: The calendar identifier.
                - summary: The human-readable calendar name.

                Returns an empty list if no calendars are found or an error occurs.
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
                    calendars.append(
                        CalendarDTO(
                            calendar_id=item.get("id"), summary=item.get("summary", "")
                        )
                    )
                page_token = response.get("nextPageToken")
                if not page_token:
                    break

            return calendars

        except Exception as e:
            self.logger.error(
                "[GoogleCalendarSyncService] unexpected error fetching calendars %s", e
            )
            return []

    def _get_calendars_events(
        self, calendar_ids: list[str], start_time: str, end_time: str
    ) -> dict[str, CalendarEventDTO]:
        """
        Fetch calendar events for multiple calendars using batched requests,
        and deduplicate them by event ID.

        This method:
        - Queries Google Calendar events for each provided calendar ID.
        - Handles pagination transparently via batch requests.
        - Filters out cancelled events.
        - Extracts Google Meet meeting codes when available.
        - Deduplicates events that appear in multiple calendars
            (e.g. shared or recurring events), preferring non-personal
            calendar ownership.

        Args:
            calendar_ids:
                A list of calendar IDs to fetch events from.
            start_time:
                RFC3339 timestamp (inclusive) representing the start of the query window.
            end_time:
                RFC3339 timestamp (exclusive) representing the end of the query window.

        Returns:
            dict[str, CalendarEventDTO]:
                A mapping from event_id to CalendarEventDTO containing:
                - event_id
                - calendar_id (resolved ownership)
                - summary
                - start time
                - recurrence flag
                - Google Meet meeting code
        """
        events_dict: dict[str, CalendarEventDTO] = {}
        requests: list[tuple] = []

        def _enqueue_page(calendar_id: str, page_token: str | None = None):
            """Enqueue a single calendar events.list request."""
            req = self.google_calendar_client.events().list(
                calendarId=calendar_id,
                timeMin=start_time,
                timeMax=end_time,
                singleEvents=True,
                orderBy="startTime",
                eventTypes="default",
                timeZone="UTC",
                pageToken=page_token,
            )
            requests.append((req, calendar_id))

        # Initialize the first page request for each calendar
        for cid in calendar_ids:
            _enqueue_page(cid)

        def _callback(request_id, response, exception):
            """Batch callback for processing calendar event responses."""
            calendar_id = request_id.split(":", 1)[0]
            if exception:
                self.logger.warning(
                    "[GoogleCalendarSyncService] batch request failed: request_id=%s, calendar_id=%s, error=%s",
                    request_id,
                    calendar_id,
                    exception,
                )
                return

            for event in response.get("items", []):
                # Skip cancelled events explicitly
                if event.get("status") == "cancelled":
                    continue

                meeting_code = self._get_meeting_code_from_event(event)
                start_str = event.get("start", {}).get("dateTime")
                if not meeting_code or not start_str:
                    continue

                eid = event.get("id")
                dto = CalendarEventDTO(
                    event_id=eid,
                    calendar_id=calendar_id,
                    summary=event.get("summary", ""),
                    start=start_str,
                    is_recurring="recurringEventId" in event,
                    meeting_code=meeting_code,
                )

                if eid in events_dict:
                    # Deduplication rule:
                    # Prefer non-personal calendar ownership over personal calendars
                    if not self._is_circlecat_email(calendar_id):
                        events_dict[eid].calendar_id = calendar_id
                else:
                    events_dict[eid] = dto

            next_token = response.get("nextPageToken")
            if next_token:
                _enqueue_page(calendar_id, next_token)

        # Execute batched requests until all pages are processed
        while requests:
            current_batch = [
                requests.pop(0) for _ in range(min(BATCH_SIZE, len(requests)))
            ]
            batch = self.google_calendar_client.new_batch_http_request(
                callback=_callback
            )
            for req_obj, cid in current_batch:
                batch.add(req_obj, request_id=f"{cid}:{uuid.uuid4()}")
            self.retry_utils.get_retry_on_transient(batch.execute)

        return events_dict

    def _get_events_attendees(
        self, events: dict[str, CalendarEventDTO], time_min: str, time_max: str
    ) -> dict[str, list[AttendanceDTO]]:
        """
        Fetch Google Meet attendance records and map them to calendar event instances.

        This method:
        - Queries Google Admin Reports API (`meet.call_ended`) in batches.
        - Retrieves attendance records grouped by Google Meet meeting code.
        - Filters participants to internal users only (circlecat.org).
        - Resolves one-to-many relationships between meeting codes and calendar
            event instances by matching join time to the closest scheduled start time
            within a fixed time window.

        Design notes:
        - A single Google Meet meeting code may correspond to multiple calendar
            event instances (e.g. recurring meetings).
        - Attendance records are assigned to the best-matching instance based on
            the smallest absolute time difference between join time and scheduled
            event start time.
        - Google Admin Reports API only retains audit logs for the last 180 days.
            Callers are expected to clamp the time range accordingly.

        Args:
            events:
                Mapping from event_id to CalendarEventDTO.
            time_min:
                RFC3339 start time (inclusive).
            time_max:
                RFC3339 end time (exclusive).

        Returns:
            dict[str, list[AttendanceDTO]]:
                Mapping from event_id to a list of AttendanceDTO records.
        """
        # Build meeting_code -> event_id(s) mapping (one code may map to multiple instances)
        code_to_event_ids: dict[str, list[str]] = {}
        for eid, dto in events.items():
            code_to_event_ids.setdefault(dto.meeting_code, []).append(eid)

        results: dict[str, list[AttendanceDTO]] = {eid: [] for eid in events.keys()}
        meeting_codes = list(code_to_event_ids.keys())

        def _callback(request_id, response, exception):
            """Batch callback for processing Meet audit log responses."""
            if exception:
                self.logger.warning(
                    "[GoogleCalendarSyncService] audit API error for meeting_code=%s: %s",
                    request_id,
                    exception,
                )
                return
            code = request_id

            target_ids = code_to_event_ids.get(code, [])
            if exception or not target_ids:
                return
            for activity in response.get("items", []):
                for meet_event in activity.get("events", []):
                    params = {
                        p.get("name"): p.get("value") or p.get("intValue")
                        for p in meet_event.get("parameters", [])
                    }

                    email = meet_event.get("actor", {}).get("email") or params.get(
                        "identifier"
                    )
                    if not email or not self._is_circlecat_email(email):
                        continue

                    # Parse actual join and leave timestamps
                    join_ts = int(params.get("start_timestamp_seconds", 0))
                    duration = int(params.get("duration_seconds", 0))
                    if join_ts == 0:
                        continue

                    ldap = email.split("@")[0]
                    join_time = datetime.fromtimestamp(join_ts, tz=timezone.utc)
                    leave_time = datetime.fromtimestamp(
                        join_ts + duration, tz=timezone.utc
                    )

                    # Match attendance to the closest event instance by start time
                    best_match_id = None
                    min_diff = MATCH_WINDOW_SECONDS

                    for eid in target_ids:
                        # Parse scheduled start time.
                        event_dto = events[eid]
                        diff = abs(join_ts - event_dto.start_ts)
                        if diff < min_diff:
                            min_diff = diff
                            best_match_id = eid

                    if best_match_id:
                        results[best_match_id].append(
                            AttendanceDTO(
                                ldap=ldap,
                                join_time=join_time,
                                leave_time=leave_time,
                            )
                        )

        # Call Google Admin Reports API in batches
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
                    startTime=time_min,
                    endTime=time_max,
                    maxResults=1000,
                )
                batch.add(req, request_id=code)
            self.retry_utils.get_retry_on_transient(batch.execute)
            time.sleep(SLEEP_BETWEEN_BATCHES)

        return results

    def _cache_calendars(self) -> list[str]:
        """
        Fetch calendar metadata from the Google Calendar API and cache it in Redis.

        This method:
        - Retrieves all accessible calendars via the Calendar API.
        - Filters out personal user calendars and system-generated calendars.
        - Caches valid calendar metadata into Redis as:
                calendar_id -> calendar summary
        - Inserts a static alias entry:
                "personal" -> "Personal Calendars"

        Returns:
            list[str]:
                A list of cached calendar IDs, excluding the synthetic "personal" entry.
        """
        calendars = self._get_calendar_list()
        filtered_ids = []
        pipeline = self.redis_client.pipeline()
        pipeline.hset(GOOGLE_CALENDAR_LIST_INDEX_KEY, "personal", "Personal Calendars")

        for cal in calendars:
            cid = cal.calendar_id
            # Skip personal user calendars or system-generated calendars
            if self._is_circlecat_email(cid) or cid.endswith(
                "@group.v.calendar.google.com"
            ):
                continue
            pipeline.hset(GOOGLE_CALENDAR_LIST_INDEX_KEY, cid, cal.summary)
            filtered_ids.append(cid)

        self.retry_utils.get_retry_on_transient(pipeline.execute)
        return filtered_ids

    def _cache_calendar_events(
        self, calendar_ids: list[str], time_min: str, time_max: str
    ) -> dict[str, CalendarEventDTO]:
        """
        Cache calendar event metadata into Redis and return the corresponding DTO map.

        This method:
        - Fetches events for the given calendars within the specified time window.
        - Normalizes recurring event IDs by stripping instance suffixes.
        - Maps personal calendars to a unified "personal" alias.
        - Caches lightweight event metadata into Redis for downstream lookups.

        Args:
            calendar_ids (list[str]):
                List of calendar IDs to fetch events from.
            time_min (str):
                RFC3339 start time (inclusive).
            time_max (str):
                RFC3339 end time (exclusive).

        Returns:
            dict[str, CalendarEventDTO]:
                A mapping from event_id to CalendarEventDTO.
        """
        all_events = self._get_calendars_events(calendar_ids, time_min, time_max)
        pipeline = self.redis_client.pipeline()

        for eid, dto in all_events.items():
            base_event_id = eid.split("_")[0]
            calendar_alias = (
                "personal"
                if self._is_circlecat_email(dto.calendar_id)
                else dto.calendar_id
            )

            pipeline.set(
                GOOGLE_CALENDAR_EVENT_DETAIL_KEY.format(event_id=base_event_id),
                json.dumps({
                    "summary": dto.summary,
                    "calendar_id": calendar_alias,
                    "is_recurring": dto.is_recurring,
                }),
            )

        self.retry_utils.get_retry_on_transient(pipeline.execute)
        return all_events

    def _cache_events_attendees(
        self, events: dict[str, CalendarEventDTO], time_min: str, time_max: str
    ):
        """
        Cache Google Meet attendance records for calendar events into Redis.

        This method:
        - Fetches attendance records for the given events within the time window.
        - Stores per-event attendance details (join/leave times) in Redis sets.
        - Indexes user participation using sorted sets for efficient queries.

        Design notes:
        - Attendance data is fetched from the Google Admin Reports API, which
            only retains audit logs for the last 180 days.
        - Events without attendance records are silently skipped.
        - Personal calendars are normalized under the "personal" alias.

        Args:
            events (dict[str, CalendarEventDTO]):
                Mapping from event_id to CalendarEventDTO.
            time_min (str):
                RFC3339 start time (inclusive).
            time_max (str):
                RFC3339 end time (exclusive).
        """

        if not events:
            return

        attendance_map = self._get_events_attendees(events, time_min, time_max)

        pipeline = self.redis_client.pipeline()

        for eid, dto in events.items():
            attendees = attendance_map.get(eid, [])
            score = dto.start_ts

            for att in attendees:
                if not att.ldap:
                    continue
                record_str = json.dumps({
                    "join_time": att.join_time.isoformat().replace("+00:00", "Z"),
                    "leave_time": att.leave_time.isoformat().replace("+00:00", "Z"),
                })
                pipeline.sadd(
                    GOOGLE_EVENT_ATTENDANCE_KEY.format(event_id=eid, ldap=att.ldap),
                    record_str,
                )

                alias = (
                    "personal"
                    if self._is_circlecat_email(dto.calendar_id)
                    else dto.calendar_id
                )
                pipeline.zadd(
                    GOOGLE_CALENDAR_USER_EVENTS_KEY.format(
                        calendar_id=alias, ldap=att.ldap
                    ),
                    {eid: score},
                )

        self.retry_utils.get_retry_on_transient(pipeline.execute)

    def pull_calendar_history(self, time_min: str = None, time_max: str = None):
        """
        Pulls and caches historical calendar event data for all calendars.

        IMPORTANT:
            Google Admin Reports API (Google Meet `call_ended` events) only retains
            audit logs for the last 180 days. As a result, attendance data older than
            180 days cannot be retrieved and synchronized, even if an earlier
            time range is provided.

            To avoid API errors, the effective synchronization window should be
            clamped to the most recent 180 days.

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
