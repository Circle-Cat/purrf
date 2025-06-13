from google.auth import default
from googleapiclient.errors import HttpError
from tenacity import retry, stop_after_attempt, wait_exponential
from src.common.logger import get_logger
from src.common.google_client import GoogleClientFactory
from datetime import datetime
from src.historical_data.constants import MEET_URL_REGEX
import re

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
            - description
            - timeZone
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
                    "description": item.get("description", ""),
                    "timeZone": item.get("timeZone"),
                })
            page_token = response.get("nextPageToken")
            if not page_token:
                break

        return calendars

    except Exception as e:
        logger.error(f"Unexpected error fetching calendars", e)
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
            title = event.get("summary", "")
            description = event.get("description", "")
            start = event.get("start", {}).get("dateTime")
            end = event.get("end", {}).get("dateTime")
            organizer = event.get("organizer", {}).get("email", "")
            is_recurring = "recurringEventId" in event

            meet_code = get_meeting_code_from_event(event)
            if meet_code:
                try:
                    attendance_data = get_event_attendance(meet_code)
                except Exception as e:
                    logger.warning(f"Failed to fetch attendance for event {event_id}: {e}")

            events.append({
                "event_id": event_id,
                "calendar_id": calendar_id,
                "title": title,
                "description": description,
                "start": start,
                "end": end,
                "attendees": attendance_data,
                "is_recurring": is_recurring,
                "organizer": organizer,
            })

        page_token = events_result.get("nextPageToken")
        if not page_token:
            break

    return events


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=3),
)
def get_event_attendance(meeting_code: str):
    """
    Fetches actual Google Meet attendance (participants) for a calendar event using the Reports API.

    Args:
        meeting_code: The unique code for the Google Meet session.

    Returns:
        A list of dictionaries containing participant details: email, duration, join/leave times.
    """
    factory = GoogleClientFactory()
    service = factory.create_reports_client()
    attendance_details = []
    next_page_token = None

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
            actor = activity.get("actor", {})
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
