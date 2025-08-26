from tenacity import retry, stop_after_attempt, wait_exponential
from backend.common.logger import get_logger
from backend.common.google_client import GoogleClientFactory
from datetime import datetime
import re
from backend.common.redis_client import RedisClientFactory
from backend.common.validation import validate_data
from backend.common.constants import (
    GOOGLE_CALENDAR_LIST_INDEX_KEY,
    GOOGLE_CALENDAR_EVENT_DETAIL_KEY,
    GOOGLE_EVENT_ATTENDANCE_KEY,
    GOOGLE_CALENDAR_USER_EVENTS_KEY,
    MicrosoftAccountStatus,
)
from backend.frontend_service.ldap_loader import (
    get_all_active_ldap_users,
    get_all_ldaps_and_displaynames,
)
import json

logger = get_logger()


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
)
def get_calendar_list():
    """
    Fetches the list of calendars accessible using the Google Calendar API.

    Returns:
        A list of calendar dictionaries, each with:
            - calendar_id
            - summary
        Returns an empty list if an error occurs or no calendars are found.
    """
    try:
        factory = GoogleClientFactory()
        service = factory.create_calendar_client()

        calendars = []
        page_token = None
        while True:
            response = service.calendarList().list(pageToken=page_token).execute()
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
        logger.error("Unexpected error fetching calendars", e)
        return []


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=3),
)
def get_calendar_events(calendar_id: str, start_time: str, end_time: str):
    """
    Fetches events for a given calendar ID and time range using the Google Calendar API.

    Args:
        calendar_id: The specific calendar's ID (e.g., 'primary' or a shared calendar ID).
        start_time: RFC3339 timestamp for the start of the range (inclusive).
        end_time: RFC3339 timestamp for the end of the range (exclusive).

    Returns:
        A list of events (dictionaries) from the calendar.
    """
    factory = GoogleClientFactory()
    service = factory.create_calendar_client()

    events = []
    page_token = None
    while True:
        events_result = (
            service.events()
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

        for event in events_result.get("items", []):
            event_id = event.get("id")
            summary = event.get("summary", "")
            start = event.get("start", {}).get("dateTime")
            attendance_data = None
            is_recurring = "recurringEventId" in event

            meet_code = get_meeting_code_from_event(event)
            if meet_code:
                try:
                    attendance_data = get_event_attendance(
                        meet_code, is_recurring, event_id
                    )
                    attendance_data = get_event_attendance(
                        meet_code, is_recurring, event_id
                    )
                except Exception as e:
                    logger.warning(
                        f"Failed to fetch attendance for event {event_id}: {e}"
                    )

            events.append({
                "event_id": event_id,
                "calendar_id": calendar_id,
                "summary": summary,
                "start": start,
                "attendees": attendance_data,
                "is_recurring": is_recurring,
            })

        page_token = events_result.get("nextPageToken")
        if not page_token:
            break

    return events


def is_circlecat_email(email: str) -> bool:
    """
    Checks whether the given email address belongs to the circlecat.org domain.

    Args:
        email: The email address to validate.

    Returns:
        True if the email ends with '@circlecat.org', False otherwise.
    """
    return email.endswith("@circlecat.org")


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=3),
)
def get_event_attendance(
    meeting_code: str, is_recurring: bool = False, event_id: str = None
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
    factory = GoogleClientFactory()
    service = factory.create_reports_client()
    attendance_details = []
    next_page_token = None

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
            logger.warning(
                f"Failed to parse recurrence date from event_id: {event_id}: {e}"
            )

    while True:
        response = (
            service.activities()
            .list(
                userKey="all",
                applicationName="meet",
                eventName="call_ended",
                filters=f"meeting_code=={meeting_code}",
                maxResults=1000,
                pageToken=next_page_token,
            )
            .execute()
        )

        activities = response.get("items", [])
        if not activities:
            logger.warning(f"No attendance data found for meeting code: {meeting_code}")
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

                email = event.get("actor", {}).get("email") or data.get("identifier")

                duration_seconds = data.get("duration_seconds", 0)
                start_ts = data.get("start_timestamp_seconds")

                join_time = (
                    datetime.utcfromtimestamp(start_ts).isoformat()
                    if start_ts
                    else None
                )
                leave_time = (
                    datetime.utcfromtimestamp(start_ts + duration_seconds).isoformat()
                    if start_ts and duration_seconds
                    else None
                )

                if recurrence_instance_date and join_time:
                    join_date = datetime.fromisoformat(join_time).date()
                    if join_date != recurrence_instance_date:
                        continue
                if email and is_circlecat_email(email):
                    attendance_details.append({
                        "email": email,
                        "duration_seconds": duration_seconds,
                        "join_time": join_time,
                        "leave_time": leave_time,
                    })

        next_page_token = response.get("nextPageToken")
        if not next_page_token:
            break

    logger.info(
        f"Fetched {len(attendance_details)} attendance records for meeting code: {meeting_code}"
    )
    return attendance_details


def get_meeting_code_from_event(event):
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
                    logger.info(
                        f"Extracted meeting code: {meeting_code} from URI: {uri}"
                    )
                    return meeting_code
        logger.warning("No valid Google Meet video entry found in the event.")
        return None
    except Exception as e:
        logger.exception(f"Error extracting meeting code from event: {e}")
        return None


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=3),
)
def cache_calendars():
    """
    Fetches calendar metadata from the Google Calendar API, filters out irrelevant calendars,
    and caches the valid calendar metadata into Redis. Also inserts a static entry: 'personal' → 'Personal Calendars'.

    Raises:
        Any exception raised by `get_calendar_list` or Redis operations will be retried up to 3 times with exponential backoff.
    """
    calendar_list = get_calendar_list()

    filtered_calendar_list = []
    ldap = None

    for calendar in calendar_list:
        calendar_id = calendar.get("calendar_id", "")
        if is_circlecat_email(calendar_id):  # Skip personal user calendars
            ldap = calendar_id.split("@")[0]
            continue
        elif calendar_id.endswith(
            "@group.v.calendar.google.com"
        ):  # Skip system-generated Google group calendars
            continue
        filtered_calendar_list.append(calendar)

    if ldap is None:
        logger.warning(
            "No calendar_id ending with @circlecat.org found; skipping caching."
        )
        return

    factory = RedisClientFactory()
    redis_client = factory.create_redis_client()
    pipeline = redis_client.pipeline()
    pipeline.hset(GOOGLE_CALENDAR_LIST_INDEX_KEY, "personal", "Personal Calendars")

    for calendar in filtered_calendar_list:
        try:
            validate_data(calendar, "calendar.schema.json")
        except Exception as e:
            logger.warning(f"Invalid calendar skipped: {e}")
            continue

        calendar_id = calendar["calendar_id"]
        pipeline.hset(GOOGLE_CALENDAR_LIST_INDEX_KEY, calendar_id, calendar["summary"])
        logger.debug(f"Cached calendar {calendar_id} for purrf")

    pipeline.execute()


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=3),
)
def cache_events(
    calendar_id: str, time_min: str, time_max: str, skip_event_ids: set = None
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
    calendar_id_alias = "personal" if is_circlecat_email(calendar_id) else calendar_id

    factory = RedisClientFactory()
    redis_client = factory.create_redis_client()
    pipeline = redis_client.pipeline()

    events = get_calendar_events(calendar_id, time_min, time_max)

    for event in events:
        event_id = event["event_id"]
        if event_id in skip_event_ids:
            continue

        skip_event_ids.add(event_id)

        try:
            validate_data(event, "calendar_event.schema.json")
        except Exception as e:
            logger.warning(f"Invalid event skipped: {e}")
            continue

        base_event_id = event_id.split("_")[0]
        pipeline.set(
            GOOGLE_CALENDAR_EVENT_DETAIL_KEY.format(event_id=base_event_id),
            json.dumps({
                "summary": event.get("summary", ""),
                "calendar_id": calendar_id_alias,
                "is_recurring": "recurringEventId" in event,
            }),
        )

        try:
            score = int(datetime.fromisoformat(event["start"]).timestamp())
        except Exception as e:
            logger.warning(f"Invalid start time for event {event_id}: {e}")
            continue

        for attendee in event.get("attendees", []):
            attendee_ldap = attendee.get("email").split("@")[0]
            if not attendee_ldap:
                continue

            attendance_key = GOOGLE_EVENT_ATTENDANCE_KEY.format(
                event_id=event_id, ldap=attendee_ldap
            )
            existing_data = redis_client.get(attendance_key)

            if existing_data:
                attendance_records = json.loads(existing_data)
            else:
                attendance_records = []

            attendance_records.append({
                "join_time": attendee["join_time"],
                "leave_time": attendee["leave_time"],
            })

            pipeline.zadd(
                GOOGLE_CALENDAR_USER_EVENTS_KEY.format(
                    calendar_id=calendar_id_alias, ldap=attendee_ldap
                ),
                {event_id: score},
            )
            pipeline.set(attendance_key, json.dumps(attendance_records))

    pipeline.execute()

    return skip_event_ids


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=3),
)
def pull_calendar_history(
    time_min: str = None, time_max: str = None, active_users: bool = True
):
    """
    Pulls and caches historical calendar event data for all calendars.

    Args:
        time_min (str): The ISO 8601 start time (inclusive) for fetching calendar events.
        time_max (str): The ISO 8601 end time (exclusive) for fetching calendar events.
        active_users (bool): If True, use only active users; otherwise, include all users.

    Raises:
        RuntimeError: If a Redis client cannot be obtained.
        Any exception raised by `cache_calendars()` or `cache_events()` will be retried up to 3 times using exponential backoff due to the `@retry` decorator.
    """
    cache_calendars()
    redis_client = RedisClientFactory().create_redis_client()
    if not redis_client:
        raise RuntimeError("Redis client not available")

    calendar_ids = redis_client.hkeys(GOOGLE_CALENDAR_LIST_INDEX_KEY)

    processed_event_ids = set()

    for calendar_id in calendar_ids:
        if calendar_id == "personal":
            continue
        processed_event_ids |= cache_events(calendar_id, time_min, time_max)

    if active_users:
        ldaps = get_all_active_ldap_users()
    else:
        ldaps = list(get_all_ldaps_and_displaynames(MicrosoftAccountStatus.ALL).keys())
    personal_calendar_ids = [f"{ldap}@circlecat.org" for ldap in ldaps]

    for personal_calendar_id in personal_calendar_ids:
        processed_event_ids |= cache_events(
            personal_calendar_id, time_min, time_max, processed_event_ids
        )
