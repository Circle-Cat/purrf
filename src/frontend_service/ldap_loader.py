from src.common.logger import get_logger
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
from src.common.redis_client import RedisClientFactory
from src.common.constants import (
    MicrosoftAccountStatus,
    MICROSOFT_LDAP_KEY,
)

logger = get_logger()


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=3),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
def get_all_ldaps_and_displaynames(status: MicrosoftAccountStatus) -> dict[str, str]:
    """
    Retrieve LDAP -> display name mappings from Redis for Microsoft accounts.

    Args:
        status (MicrosoftAccountStatus): The account status to filter by.
            - ACTIVE: returns only active user mappings.
            - TERMINATED: returns only terminated user mappings.
            - ALL: returns both active and terminated user mappings merged.

    Returns:
        dict[str, str]: A dictionary mapping LDAP to display name,
                        containing entries according to the given status.

    Raises:
        ValueError: If Redis client is not available or if an unsupported status is passed.
    """
    redis_client = RedisClientFactory().create_redis_client()
    if not redis_client:
        raise ValueError("Redis client not created.")

    result = {}

    statuses = []
    if status == MicrosoftAccountStatus.ALL:
        statuses = [MicrosoftAccountStatus.ACTIVE, MicrosoftAccountStatus.TERMINATED]
    elif status in [MicrosoftAccountStatus.ACTIVE, MicrosoftAccountStatus.TERMINATED]:
        statuses = [status]
    else:
        raise ValueError(f"Unsupported status: {status}")

    for s in statuses:
        entries = redis_client.hgetall(
            MICROSOFT_LDAP_KEY.format(account_status=s.value)
        )
        if entries:
            result.update(entries)

    return result


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=3),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
def get_all_active_ldap_users() -> list[str]:
    """
    Returns all active Microsoft LDAPs by pulling the field names from the Redis hash.
    """
    redis_client = RedisClientFactory().create_redis_client()
    if not redis_client:
        raise ValueError("Redis client not created.")

    redis_key = MICROSOFT_LDAP_KEY.format(
        account_status=MicrosoftAccountStatus.ACTIVE.value
    )
    return redis_client.hkeys(redis_key)
