from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
from backend.common.redis_client import RedisClientFactory
from backend.common.constants import (
    GOOGLE_CALENDAR_LIST_INDEX_KEY,
    GOOGLE_CALENDAR_USER_EVENTS_KEY,
    GOOGLE_EVENT_ATTENDANCE_KEY,
    GOOGLE_CALENDAR_EVENT_DETAIL_KEY,
)
import json
from datetime import datetime


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=3),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
def get_all_calendars() -> list[dict[str, str]]:
    """
    Retrieve the calendar list from Redis.

    Returns:
        list[dict[str, str]]: A list of dictionaries with 'id' and 'name' keys.

    Raises:
        ValueError: If Redis client is not created or LDAP is missing.
    """
    redis_client = RedisClientFactory().create_redis_client()
    if not redis_client:
        raise ValueError("Redis client not created.")

    calendar_data = redis_client.hgetall(GOOGLE_CALENDAR_LIST_INDEX_KEY)

    calendars = [{"id": key, "name": value} for key, value in calendar_data.items()]

    return calendars


def get_all_events(
    calendar_id: str, ldaps: list[str], start_date: str, end_date: str
) -> dict[str, list[dict[str, any]]]:
    """
    Fetch all events with attendance info for given calendar, ldaps, and date range using Redis pipeline.

    Args:
        calendar_id (str): The calendar ID.
        ldaps (List[str]): List of LDAP usernames.
        start_date (str): Start date in ISO format (inclusive).
        end_date (str): End date in ISO format (inclusive).

    Returns:
        Dict[str, List[Dict]]: Each LDAP maps to a list of event dicts with id, date, join/leave times.
    """
    factory = RedisClientFactory()
    redis_client = factory.create_redis_client()
    result: dict[str, list[dict[str, any]]] = {}

    try:
        start_ts = int(datetime.fromisoformat(start_date).timestamp())
        end_ts = int(datetime.fromisoformat(end_date).timestamp())
    except ValueError as e:
        raise ValueError(f"Invalid start or end date format: {e}")

    pipeline = redis_client.pipeline()
    events_key_by_ldap = {
        ldap: GOOGLE_CALENDAR_USER_EVENTS_KEY.format(calendar_id=calendar_id, ldap=ldap)
        for ldap in ldaps
    }

    for events_key in events_key_by_ldap.values():
        pipeline.zrangebyscore(events_key, min=start_ts, max=end_ts)

    ldap_event_id_lists = pipeline.execute()
    ldap_event_ids_map = dict(zip(ldaps, ldap_event_id_lists))

    attendance_keys = []
    attendance_key_to_ldap_event = {}
    all_base_event_ids = set()

    for ldap, event_ids in ldap_event_ids_map.items():
        for event_id in event_ids:
            key = GOOGLE_EVENT_ATTENDANCE_KEY.format(event_id=event_id, ldap=ldap)
            attendance_keys.append(key)
            attendance_key_to_ldap_event[key] = (ldap, event_id)
            base_event_id = event_id.split("_")[0]
            all_base_event_ids.add(base_event_id)

    pipeline = redis_client.pipeline()
    for key in attendance_keys:
        pipeline.get(key)

    attendance_results = pipeline.execute()
    attendance_data_map = {}  # (ldap, event_id) -> attendance_record

    for key, raw_data in zip(attendance_keys, attendance_results):
        ldap, event_id = attendance_key_to_ldap_event[key]
        if not raw_data:
            continue
        try:
            attendance_record = json.loads(raw_data)
            attendance_data_map[(ldap, event_id)] = attendance_record
        except json.JSONDecodeError:
            continue

    event_detail_keys = [
        GOOGLE_CALENDAR_EVENT_DETAIL_KEY.format(event_id=base_id)
        for base_id in all_base_event_ids
    ]

    pipeline = redis_client.pipeline()
    for key in event_detail_keys:
        pipeline.get(key)

    event_detail_results = pipeline.execute()
    base_event_detail_map = {}

    for base_id, raw_data in zip(all_base_event_ids, event_detail_results):
        if not raw_data:
            continue
        try:
            base_event_detail_map[base_id] = json.loads(raw_data)
        except json.JSONDecodeError:
            continue

    for ldap in ldaps:
        user_events = []
        for event_id in ldap_event_ids_map.get(ldap, []):
            attendance = attendance_data_map.get((ldap, event_id))
            if not attendance:
                continue

            base_event_id = event_id.split("_")[0]
            event_detail = base_event_detail_map.get(base_event_id)
            if not event_detail:
                continue

            user_events.append({
                "event_id": event_id,
                "summary": event_detail.get("summary", ""),
                "calendar_id": event_detail.get("calendar_id", ""),
                "is_recurring": event_detail.get("is_recurring", False),
                "attendance": attendance,
            })

        result[ldap] = user_events

    return result
