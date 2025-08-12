from backend.common.redis_client import RedisClientFactory
from datetime import datetime, timezone
from dateutil.relativedelta import relativedelta
from backend.utils.google_chat_utils import get_chat_spaces
from backend.common.logger import get_logger
from backend.common.constants import CREATED_GOOGLE_CHAT_MESSAGES_INDEX_KEY
from backend.frontend_service.ldap_loader import get_all_ldaps_and_displaynames
from backend.common.constants import MicrosoftAccountStatus

logger = get_logger()


def count_messages_in_date_range(
    space_ids: list[str] | None = None,
    sender_ldaps: list[str] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict[str, dict[str, int]]:
    """
    Count the number of messages in Redis sorted sets for each sender/space
    pair within a specified date range, using Redis-side ZCOUNT for efficient
    filtering.

    Each Redis key is formatted as CREATED_GOOGLE_CHAT_MESSAGES_INDEX_KEY, representing a
    sorted set where each element corresponds to a message with a UNIX
    timestamp as its score.

    Args:
        space_ids (list[str] | None): List of space IDs whose messages
            should be counted. If None, all available space IDs will be
            retrieved using `get_chat_spaces()`. Entries with only whitespace
            will be ignored.
        sender_ldaps (list[str] | None): List of sender LDAPs to include
            in the count. If None, all active Microsoft LDAPs will be retrieved
            as the default. Entries with only whitespace will be ignored.
        start_date (str | None): Start date of the range, in "YYYY-MM-DD"
            format. Defaults to one month before `end_date`.
        end_date (str | None): End date of the range, in "YYYY-MM-DD"
            format. Defaults to the current date (UTC).

    Returns:
        dict[str, dict[str, int]]: A nested dictionary mapping each
        `sender_ldap` (user) to another dictionary, which maps each
        `space_id` (chat room) to the number of messages the user sent within
        the specified date range. All sender/space combinations are included,
        even if the count is zero.

    Raises:
        RuntimeError: If Redis client creation fails.
        RuntimeError: If fetching space IDs from Google Chat fails.
        RuntimeError: If fetching LDAPs from the directory fails.
        ValueError: If the date format is invalid.
    """

    # Input cleanup: remove empty or whitespace-only entries
    space_ids = [s.strip() for s in space_ids or [] if s.strip()]
    sender_ldaps = [s.strip() for s in sender_ldaps or [] if s.strip()]

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
        logger.error(f"Failed to initialize Redis client: {e}")
        raise RuntimeError("Failed to connect to Redis service") from e

    if not space_ids:
        logger.info("[API] Fetching all space IDs via get_chat_spaces()...")
        try:
            space_dict = get_chat_spaces(space_type="SPACE", page_size=100)
            space_ids = list(space_dict.keys())
        except Exception as e:
            error_msg = f"Failed to fetch space IDs from get_chat_spaces(): {e}"
            logger.error(error_msg)
            raise RuntimeError(
                "Failed to fetch space IDs from get_chat_spaces()"
            ) from e

    if not sender_ldaps:
        logger.info("[API] Fetching active Microsoft LDAPs as default sender list...")
        try:
            active_ldaps = get_all_ldaps_and_displaynames(MicrosoftAccountStatus.ACTIVE)
            sender_ldaps = list(active_ldaps.keys())
            logger.info(f"[API] Found {len(sender_ldaps)} active Microsoft LDAPs")
        except Exception as e:
            logger.error(
                f"Failed to fetch active Microsoft LDAPs: {e}. "
                f"This indicates a data consistency issue in the system."
            )
            raise RuntimeError(
                f"Failed to fetch sender LDAPs from Microsoft directory. "
                f"This indicates a data consistency issue that needs to be resolved: {e}"
            ) from e

    # Use Redis pipeline for optimized querying
    pipeline = redis_client.pipeline()
    query_keys: list[tuple[str, str]] = []

    # Build pipeline queries
    for space_id in space_ids:
        for sender_ldap in sender_ldaps:
            redis_key = CREATED_GOOGLE_CHAT_MESSAGES_INDEX_KEY.format(
                space_id=space_id, sender_ldap=sender_ldap
            )
            pipeline.zcount(redis_key, start_dt.timestamp(), end_dt.timestamp())
            query_keys.append((space_id, sender_ldap))

    # Execute pipeline and process results
    try:
        pipeline_results = pipeline.execute()
        logger.info(f"[API] Executed pipeline with {len(query_keys)} queries")

        # Initialize result and assign values directly
        result: dict[str, dict[str, int]] = {}
        for i, (space_id, sender_ldap) in enumerate(query_keys):
            count = pipeline_results[i]

            # Initialize sender_ldap dict if not exists
            if sender_ldap not in result:
                result[sender_ldap] = {}

            result[sender_ldap][space_id] = count

    except Exception as e:
        logger.error(f"Failed to execute Redis pipeline: {e}")
        raise RuntimeError("Failed to execute Redis pipeline queries") from e

    return result
