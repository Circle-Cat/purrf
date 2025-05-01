from redis_dal.redis_client_factory import RedisClientFactory
from datetime import datetime, timezone
from dateutil.relativedelta import relativedelta
from google.chat_utils import get_chat_spaces, list_directory_all_people_ldap
import logging
import time
from typing import List, Dict, Optional


def count_messages_in_date_range(
    space_ids: Optional[List[str]] = None,
    sender_ldaps: Optional[List[str]] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Dict[str, Dict[str, int]]:
    """
    Count the number of messages in Redis sorted sets for each sender/space pair within a specified date range,
    using Redis-side ZCOUNT for efficient filtering.

    Each Redis key is formatted as "{space_id}/{sender_ldap}", representing a sorted set where each element corresponds
    to a message with a UNIX timestamp as its score.

    Args:
        space_ids (Optional[List[str]]): List of space IDs whose messages should be counted.
            If None, all available space IDs will be retrieved using `get_chat_spaces()`.
        sender_ldaps (Optional[List[str]]): List of sender LDAPs to include in the count.
            If None, all LDAPs will be retrieved using `list_directory_all_people_ldap()`.
        start_date (Optional[str]): Start date of the range, in "YYYY-MM-DD" format.
            Defaults to one month before `end_date`.
        end_date (Optional[str]): End date of the range, in "YYYY-MM-DD" format.
            Defaults to the current date (UTC).

    Returns:
        Dict[str, Dict[str, int]]: A nested dictionary mapping each `sender_ldap` (user) to another dictionary,
        which maps each `space_id` (chat room) to the number of messages the user sent within the specified date range.
        All sender/space combinations are included, even if the count is zero.

    Raises:
        RuntimeError: If Redis client creation fails.
        RuntimeError: If fetching space IDs from Google Chat fails.
        RuntimeError: If fetching LDAPs from the directory fails.
        ValueError: If the date format is invalid.
    """

    today = datetime.now(timezone.utc)
    end_dt = (
        datetime.strptime(end_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        if end_date
        else today
    )
    start_dt = (
        datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        if start_date
        else end_dt - relativedelta(months=1)
    )

    try:
        redis_client = RedisClientFactory().create_redis_client()
    except Exception as e:
        logging.error(f"Failed to initialize Redis client: {e}")
        raise RuntimeError("Failed to connect to Redis service") from e

    if space_ids is None:
        logging.info("[API] Fetching all space IDs via get_chat_spaces()...")
        try:
            space_dict = get_chat_spaces(space_type="SPACE", page_size=100)
            space_ids = list(space_dict.keys())
        except Exception as e:
            logging.error(f"Failed to fetch space IDs from get_chat_spaces(): {e}")
            raise RuntimeError(
                "Failed to fetch space IDs from get_chat_spaces()"
            ) from e

    if sender_ldaps is None:
        logging.info(
            "[API] Fetching all sender LDAPs via list_directory_all_people_ldap()..."
        )
        try:
            all_people_dict = list_directory_all_people_ldap()
            sender_ldaps = list(set(all_people_dict.values()))
        except Exception as e:
            logging.error(
                f"Failed to fetch sender LDAPs from list_directory_all_people_ldap(): {e}"
            )
            raise RuntimeError(
                "Failed to fetch sender LDAPs from list_directory_all_people_ldap()"
            ) from e

    result: Dict[str, Dict[str, int]] = {}
    total_start_time = time.time()

    for space_id in space_ids:
        for sender_ldap in sender_ldaps:
            redis_key = f"{space_id}/{sender_ldap}"

            count = redis_client.zcount(
                redis_key, start_dt.timestamp(), end_dt.timestamp()
            )

            if sender_ldap not in result:
                result[sender_ldap] = {}
            result[sender_ldap][space_id] = count

    total_elapsed = time.time() - total_start_time

    return result
