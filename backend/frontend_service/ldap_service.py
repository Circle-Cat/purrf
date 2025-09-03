import itertools

from backend.common.constants import (
    MicrosoftAccountStatus,
    MicrosoftGroups,
    LDAP_KEY_TEMPLATE,
)


class LdapService:
    def __init__(self, logger, redis_client, retry_utils):
        """
        Initializes the LdapService with necessary clients and logger.

        Args:
            logger: The logger instance for logging messages.
            redis_client: The Redis client instance.
            retry_utils: A RetryUtils for handling retries on transient errors.
        """
        self.logger = logger
        self.redis_client = redis_client
        self.retry_utils = retry_utils

    def get_ldaps_by_status_and_group(
        self,
        status: MicrosoftAccountStatus,
        groups: list[MicrosoftGroups],
    ) -> dict[str, dict[str, dict[str, str]]]:
        """
        Retrieve LDAP username mappings stored in Redis, filtered by account status and group.

        This method returns a nested dictionary containing LDAP information grouped first by Microsoft group
        (e.g., interns, employees, volunteers), then by account status (e.g., active, terminated). It queries Redis
        using hash keys formatted as `LDAP_KEY_TEMPLATE`, and aggregates the data accordingly.

        If `status` is `MicrosoftAccountStatus.ALL`, it includes `ACTIVE` and `TERMINATED`.

        Args:
            status (MicrosoftAccountStatus): The account status to filter by (e.g., ACTIVE, TERMINATED, ALL).
            groups (List[MicrosoftGroups]): The Microsoft group list to filter by (e.g., INTERNS, EMPLOYEES, VOLUNTEERS).

        Returns:
            dict[str, dict[str, dict[str, str]]]: A nested dictionary of LDAP records organized as:
                {
                    "<group>": {
                        "<status>": {
                            "<ldap1>": "<name_1>",
                            "<ldap2>": "<name_2>",
                            ...
                        },
                        ...
                    },
                    ...
                }

        Example:
            >>> service.get_ldaps_by_status_and_group(
                    status=MicrosoftAccountStatus.ACTIVE,
                    groups=[MicrosoftGroups.EMPLOYEES, MicrosoftGroups.INTERNS]
                )
            {
                "employees": {
                    "active": {
                        "user123": "jdoe",
                        "user456": "asmith"
                    }
                }
            }
        """
        if not isinstance(status, MicrosoftAccountStatus):
            raise TypeError("Status must be a MicrosoftAccountStatus enum value.")
        if not groups or not all(isinstance(g, MicrosoftGroups) for g in groups):
            raise TypeError("All groups must be MicrosoftGroups enum values.")

        status_list = (
            [status]
            if status != MicrosoftAccountStatus.ALL
            else [
                MicrosoftAccountStatus.ACTIVE,
                MicrosoftAccountStatus.TERMINATED,
            ]
        )

        self.logger.debug(f"Resolved groups: {[g.value for g in groups]}")
        self.logger.debug(f"Resolved status_list: {[s.value for s in status_list]}")

        pipeline = self.redis_client.pipeline()
        key_map = {}

        for group, status in itertools.product(groups, status_list):
            key = LDAP_KEY_TEMPLATE.format(
                account_status=status.value, group=group.value
            )
            pipeline.hgetall(key)
            key_map[key] = (group.value, status.value)

        results = self.retry_utils.get_retry_on_transient(pipeline.execute)

        organized_results = {}
        for key, hash_dict in zip(key_map.keys(), results):
            group_val, status_val = key_map[key]
            self.logger.debug(f"Results for {group_val}/{status_val}: {hash_dict}")

            if group_val not in organized_results:
                organized_results[group_val] = {}
            organized_results[group_val][status_val] = hash_dict

        return organized_results

    def get_all_ldaps(self) -> list[str]:
        """
        Retrieve all LDAPs across all Microsoft groups and both ACTIVE and TERMINATED statuses.

        Returns:
            list[str]: Unique list of LDAP identifiers.
        """
        keys: list[str] = []
        for group in MicrosoftGroups:
            for status in (
                MicrosoftAccountStatus.ACTIVE,
                MicrosoftAccountStatus.TERMINATED,
            ):
                keys.append(
                    LDAP_KEY_TEMPLATE.format(
                        account_status=status.value,
                        group=group.value,
                    )
                )

        pipeline = self.redis_client.pipeline()
        for k in keys:
            pipeline.hkeys(k)

        results = self.retry_utils.get_retry_on_transient(pipeline.execute)

        ldap_set: set[str] = set()
        if results:
            for ldaps in results:
                if ldaps:
                    ldap_set.update(ldaps)

        return list(ldap_set)

    def get_active_interns_ldaps(self) -> list[str]:
        """
        Retrieve all LDAPs for active interns directly from Redis.

        Returns:
            list[str]: List of LDAP identifiers for active interns.
        """
        redis_key = LDAP_KEY_TEMPLATE.format(
            account_status=MicrosoftAccountStatus.ACTIVE.value,
            group=MicrosoftGroups.INTERNS.value,
        )
        ldaps = self.retry_utils.get_retry_on_transient(
            self.redis_client.hkeys, redis_key
        )
        return ldaps if ldaps else []
