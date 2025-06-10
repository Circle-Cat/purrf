from google.auth import default
from tenacity import retry, stop_after_attempt, wait_exponential
from src.common.logger import get_logger
from src.common.google_client import GoogleClientFactory

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
        logger.error(f"Unexpected error fetching calendars")
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

        events.extend(events_result.get("items", []))

        page_token = events_result.get("nextPageToken")
        if not page_token:
            break

    return events

