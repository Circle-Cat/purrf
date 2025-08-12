from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
from backend.common.redis_client import RedisClientFactory
from backend.common.constants import (
    GOOGLE_USER_CALENDARS_INDEX_KEY,
    GOOGLE_CALENDAR_LIST_KEY,
)
import json


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=3),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
def get_calendars_for_user(ldap: str) -> list[dict]:
    """
    Retrieve the calendar list for a specific user from Redis.

    Args:
        ldap (str): The user's LDAP.

    Returns:
        list[dict]: A list of calendar metadata dictionaries.

    Raises:
        ValueError: If Redis client is not created or LDAP is missing.
    """
    if not ldap:
        raise ValueError("Missing LDAP.")

    redis_client = RedisClientFactory().create_redis_client()
    if not redis_client:
        raise ValueError("Redis client not created.")

    calendar_ids = redis_client.zrange(
        GOOGLE_USER_CALENDARS_INDEX_KEY.format(ldap=ldap), 0, -1
    )
    if not calendar_ids:
        return []

    keys = [
        GOOGLE_CALENDAR_LIST_KEY.format(calendar_id=calendar_id)
        for calendar_id in calendar_ids
    ]

    with redis_client.pipeline() as pipe:
        for key in keys:
            pipe.get(key)
        results = pipe.execute()

    calendars = []
    for raw in results:
        if raw:
            calendars.append(json.loads(raw))

    return calendars
