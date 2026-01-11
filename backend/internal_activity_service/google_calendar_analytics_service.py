from backend.common.constants import (
    GOOGLE_CALENDAR_LIST_INDEX_KEY,
    GOOGLE_CALENDAR_USER_EVENTS_KEY,
    GOOGLE_EVENT_ATTENDANCE_KEY,
    GOOGLE_CALENDAR_EVENT_DETAIL_KEY,
)
import json
from datetime import datetime


class GoogleCalendarAnalyticsService:
    def __init__(self, logger, redis_client, retry_utils):
        """
        Initialize the GoogleCalendarAnalyticsService with necessary clients and logger.

        Args:
            logger: The logger instance for logging messages.
            redis_client: The Redis client instance.
            retry_utils: A RetryUtils for handling retries on transient errors.
        """
        self.logger = logger
        self.redis_client = redis_client
        self.retry_utils = retry_utils

        if not logger:
            raise ValueError("Logger not provided.")
        if not self.redis_client:
            raise ValueError("Redis client not created.")
        if not self.retry_utils:
            raise ValueError("Retry utils not provided.")

    def _get_calendar_name(self, calendar_id: str) -> str:
        """
        Retrieve the calendar's display name from the Redis hash that stores all calendars.

        Args:
            calendar_id (str): Google Calendar ID.

        Returns:
            str: Calendar name.
        """
        name = self.retry_utils.get_retry_on_transient(
            self.redis_client.hget,
            GOOGLE_CALENDAR_LIST_INDEX_KEY,
            calendar_id,
        )
        return name

    def get_all_calendars(self) -> list[dict[str, str]]:
        """
        Retrieve the calendar list from Redis.

        Returns:
            list[dict[str, str]]: A list of dictionaries with 'id' and 'name' keys.

        Raises:
            ValueError: If Redis client is not created or LDAP is missing.
        """
        calendar_data = self.retry_utils.get_retry_on_transient(
            self.redis_client.hgetall, GOOGLE_CALENDAR_LIST_INDEX_KEY
        )
        calendars = [{"id": key, "name": value} for key, value in calendar_data.items()]
        return calendars

    def get_all_events(
        self,
        calendar_id: str,
        ldaps: list[str],
        start_date: datetime,
        end_date: datetime,
    ) -> dict[str, list[dict[str, any]]]:
        """
        Fetch all events with attendance info for given calendar, ldaps, and date range using Redis pipeline.

        Args:
            calendar_id (str): The calendar ID.
            ldaps (List[str]): List of LDAP usernames.
            start_date (datetime): Start date in ISO format (inclusive).
            end_date (datetime): End date in ISO format (inclusive).

        Returns:
            Dict[str, List[Dict]]: Each LDAP maps to a list of event dicts with id, date, join/leave times.
        """
        result: dict[str, list[dict[str, any]]] = {}

        start_ts = int(start_date.timestamp())
        end_ts = int(end_date.timestamp())

        pipeline = self.redis_client.pipeline()
        events_key_by_ldap = {
            ldap: GOOGLE_CALENDAR_USER_EVENTS_KEY.format(
                calendar_id=calendar_id, ldap=ldap
            )
            for ldap in ldaps
        }

        for events_key in events_key_by_ldap.values():
            pipeline.zrange(events_key, start_ts, end_ts, byscore=True)

        ldap_event_id_lists = self.retry_utils.get_retry_on_transient(pipeline.execute)
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

        pipeline = self.redis_client.pipeline()
        for key in attendance_keys:
            pipeline.smembers(key)

        attendance_results = self.retry_utils.get_retry_on_transient(pipeline.execute)
        attendance_data_map = {}  # (ldap, event_id) -> attendance_record

        for key, raw_members in zip(attendance_keys, attendance_results):
            ldap, event_id = attendance_key_to_ldap_event[key]
            if raw_members:
                records: list[dict[str, any]] = []
                for member in raw_members:
                    try:
                        records.append(json.loads(member))
                    except json.JSONDecodeError:
                        self.logger.warning(
                            f"Failed to decode attendance data for {key}"
                        )
                        continue
                if records:
                    attendance_data_map[(ldap, event_id)] = records

        event_detail_keys = [
            GOOGLE_CALENDAR_EVENT_DETAIL_KEY.format(event_id=base_id)
            for base_id in all_base_event_ids
        ]

        pipeline = self.redis_client.pipeline()
        for key in event_detail_keys:
            pipeline.get(key)

        event_detail_results = self.retry_utils.get_retry_on_transient(pipeline.execute)
        base_event_detail_map = {}

        for base_id, raw_data in zip(all_base_event_ids, event_detail_results):
            if raw_data:
                try:
                    base_event_detail_map[base_id] = json.loads(raw_data)
                except json.JSONDecodeError:
                    self.logger.warning(f"Failed to decode event detail for {base_id}")
                    continue

        calendar_name = self._get_calendar_name(calendar_id)

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
                    "calendar_name": calendar_name,
                    "is_recurring": event_detail.get("is_recurring", False),
                    "attendance": attendance,
                })

            result[ldap] = user_events

        return result

    def get_all_events_from_calendars(
        self,
        calendar_ids: list[str],
        ldaps: list[str],
        start_date: datetime,
        end_date: datetime,
    ) -> dict[str, list[dict[str, any]]]:
        """
        Fetch all events (with attendance info) for multiple calendars.

        Args:
            calendar_id (List[str]): List of calendar ID.
            ldaps (List[str]): List of LDAP usernames.
            start_date (datetime): Start date in ISO format (inclusive).
            end_date (datetime): End date in ISO format (inclusive).

        Returns:
            Dict[str, List[Dict]]: Each LDAP maps to a list of event dicts.
        """
        combined_result: dict[str, list[dict[str, any]]] = {ldap: [] for ldap in ldaps}

        for cal_id in calendar_ids:
            single_result = self.get_all_events(
                cal_id,
                ldaps,
                start_date,
                end_date,
            )
            for ldap, events in single_result.items():
                combined_result[ldap].extend(events)

        return combined_result

    def get_meeting_hours_for_user(
        self,
        calendar_ids: list[str],
        ldap_list: list[str],
        start_date: datetime,
        end_date: datetime,
    ) -> dict[str, float]:
        """
        Compute total meeting hours for each LDAP user across multiple calendars.

        Args:
            calendar_ids (List[str]): List of calendar IDs to include.
            ldap_list (List[str]): List of LDAP usernames.
            start_date (datetime): Start datetime (inclusive).
            end_date (datetime): End datetime (inclusive).

        Returns:
            Dict[str, float]: Mapping of LDAP -> total meeting hours.
        """
        meeting_hours_by_user = {ldap: 0.0 for ldap in ldap_list}

        all_events = self.get_all_events_from_calendars(
            calendar_ids=calendar_ids,
            ldaps=ldap_list,
            start_date=start_date,
            end_date=end_date,
        )

        for ldap in ldap_list:
            events = all_events.get(ldap, [])
            total_hours = 0.0

            for event in events:
                attendance = event.get("attendance", [])
                for rec in attendance:
                    if "join_time" in rec and "leave_time" in rec:
                        join = datetime.fromisoformat(rec["join_time"])
                        leave = datetime.fromisoformat(rec["leave_time"])
                        total_hours += (leave - join).total_seconds() / 3600.0

            meeting_hours_by_user[ldap] = round(total_hours, 2)

        return meeting_hours_by_user
