from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
from backend.common.redis_client import RedisClientFactory
from backend.common.constants import (
    GOOGLE_CALENDAR_LIST_INDEX_KEY,
)


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
