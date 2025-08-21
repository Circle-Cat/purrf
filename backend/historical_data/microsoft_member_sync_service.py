import asyncio
from backend.common.constants import (
    MicrosoftAccountStatus,
    MicrosoftGroups,
    LDAP_KEY_TEMPLATE,
)


class MicrosoftMemberSyncService:
    """
    Synchronizes Microsoft 365 user information with Redis.

    This class integrates with Microsoft Graph API to fetch the latest
    members, classifies them into groups and account statuses, and
    ensures Redis is updated incrementally (add, update, delete).
    """

    def __init__(self, logger, redis_client, microsoft_service, retry_utils):
        """
        Initializes the MicrosoftMemberService with necessary clients and logger.

        Args:
            logger: The logger instance for logging messages.
            redis_client: The Redis client instance.
            microsoft_service: The MicrosoftService instance.
            retry_utils: A RetryUtils for handling retries on transient errors.
        """
        self.logger = logger
        self.redis_client = redis_client
        self.microsoft_service = microsoft_service
        self.retry_utils = retry_utils
        self.storage_groups = [group.value for group in MicrosoftGroups]
        self.storage_statuses = [
            MicrosoftAccountStatus.ACTIVE.value,
            MicrosoftAccountStatus.TERMINATED.value,
        ]
        self.status_group_pairs = [
            (status, group)
            for status in self.storage_statuses
            for group in self.storage_groups
        ]

    def get_current_redis_members_by_group_and_status(
        self,
    ) -> dict[tuple[str, str], dict]:
        """
        Retrieves currently cached user data from Redis.

        For each (status, group) pair, this fetches a Redis hash where
        keys are `ldap` (string) and values are `display_name` (string).

        Returns:
            dict[tuple[str, str], dict]:
                A mapping from (status, group) -> {ldap: display_name}.
                Example: {("active", "interns"): {"alice": "Alice Doe", ...}}

        Notes:
            - Uses pipeline for batch Redis queries.
            - Resilient to transient Redis failures via retry_utils.
        """
        pipe = self.redis_client.pipeline()
        redis_keys_to_fetch = []

        for status, group in self.status_group_pairs:
            redis_key = LDAP_KEY_TEMPLATE.format(account_status=status, group=group)
            pipe.hgetall(redis_key)
            redis_keys_to_fetch.append((status, group))

        redis_results = self.retry_utils.get_retry_on_transient(pipe.execute)

        all_current_redis_members = {}

        for i, (status, group) in enumerate(redis_keys_to_fetch):
            all_current_redis_members[(status, group)] = redis_results[i]

        self.logger.debug(f"all_current_redis_members: {all_current_redis_members}")

        return all_current_redis_members

    async def get_latest_members_by_group_and_status(
        self,
    ) -> dict[tuple[str, str], dict]:
        """
        Fetch the latest Microsoft 365 members from Graph API and
        classify them by (status, group).

        Workflow:
        - Fetch all groups from Microsoft Graph.
        - Identify target groups (interns, employees).
        - Fetch members of each target group.
        - Determine each member's account status (active/terminated).
        - Build mapping keyed by (status, group).

        Returns:
            dict[tuple[str, str], dict]:
                Latest members grouped by status and group.
                Example: {("terminated", "employees"): {"bob": "Bob Lee", ...}}

        Raises:
            RuntimeError:
                If no members are returned by Graph API.
            ValueError:
                If critical groups (Interns or Employees) are missing.
        """
        all_groups = await self.microsoft_service.list_all_groups()
        latest_members_info = await self.microsoft_service.get_all_microsoft_members()

        if not latest_members_info:
            self.logger.error(
                "No Microsoft 365 users found matching the domain filter."
            )
            raise RuntimeError("No Microsoft 365 users were fetched from Graph API.")

        target_group_ids = {}
        required_groups = {
            MicrosoftGroups.INTERNS.value,
            MicrosoftGroups.EMPLOYEES.value,
        }

        for group in all_groups:
            name = group.display_name.lower()
            if name in required_groups:
                target_group_ids[name] = group.id
                self.logger.debug(f"Found group info: {group}")

        missing = required_groups - target_group_ids.keys()
        if missing:
            raise ValueError(f"Missing required groups: {', '.join(missing)}")

        interns_info, employees_info = await asyncio.gather(
            self.microsoft_service.get_group_members(
                target_group_ids[MicrosoftGroups.INTERNS.value]
            ),
            self.microsoft_service.get_group_members(
                target_group_ids[MicrosoftGroups.EMPLOYEES.value]
            ),
        )

        interns_ids = {member.id for member in interns_info}
        employee_ids = {member.id for member in employees_info}

        new_members_by_group_and_status = {}
        for status, group in self.status_group_pairs:
            new_members_by_group_and_status[(status, group)] = {}

        for member in latest_members_info:
            if not member.mail or "@" not in member.mail:
                continue

            ldap = member.mail.split("@")[0]
            display_name = member.display_name

            member_group = None
            if member.id in interns_ids:
                member_group = MicrosoftGroups.INTERNS.value
            elif member.id in employee_ids:
                member_group = MicrosoftGroups.EMPLOYEES.value
            else:
                member_group = MicrosoftGroups.VOLUNTEERS.value

            member_status = (
                MicrosoftAccountStatus.ACTIVE.value
                if member.account_enabled
                else MicrosoftAccountStatus.TERMINATED.value
            )

            if member_group and member_status:
                new_members_by_group_and_status[(member_status, member_group)][ldap] = (
                    display_name
                )

        self.logger.debug(
            f"Latest members by group and status: {new_members_by_group_and_status}"
        )
        return new_members_by_group_and_status

    async def sync_microsoft_members_to_redis(self):
        """
        Synchronize Microsoft 365 members with Redis via incremental update.

        - Compare latest Graph API data with current Redis data.
        - Update Redis with new/changed members.
        - Delete stale members no longer present in Graph API.

        Logging:
            - Logs newly added, updated, and deleted members.
            - Logs summary of sync completion or no-op.

        Notes:
            - Redis updates are pipelined for efficiency.
            - No changes are committed if nothing differs.
        """
        current_redis_saved_members = (
            self.get_current_redis_members_by_group_and_status()
        )
        new_members_by_group_and_status = (
            await self.get_latest_members_by_group_and_status()
        )

        pipe = self.redis_client.pipeline()
        changes_made = False

        for (status, group), new_data in new_members_by_group_and_status.items():
            redis_key = LDAP_KEY_TEMPLATE.format(account_status=status, group=group)
            old_data = current_redis_saved_members.get((status, group), {})

            old_set = set(old_data.keys())
            new_set = set(new_data.keys())

            members_to_delete = old_set - new_set
            if members_to_delete:
                pipe.hdel(redis_key, *members_to_delete)
                changes_made = True
                self.logger.info(
                    f"Deleted {len(members_to_delete)} members from Redis key '{redis_key}'."
                )
                self.logger.debug(f"Deleted members: {', '.join(members_to_delete)}")

            members_to_add_or_update = {
                ldap: display_name
                for ldap, display_name in new_data.items()
                if old_data.get(ldap) != display_name
            }

            if members_to_add_or_update:
                pipe.hset(redis_key, mapping=members_to_add_or_update)
                changes_made = True

                newly_added_members = set(members_to_add_or_update.keys()) - old_set
                updated_members = set(members_to_add_or_update.keys()) & old_set

                if newly_added_members:
                    self.logger.info(
                        f"Added {len(newly_added_members)} new members to Redis key '{redis_key}'."
                    )
                    self.logger.debug(f"Newly added: {', '.join(newly_added_members)}")

                if updated_members:
                    self.logger.info(
                        f"Updated {len(updated_members)} members in Redis key '{redis_key}'."
                    )
                    self.logger.debug(f"Updated members: {', '.join(updated_members)}")

        if changes_made:
            self.retry_utils.get_retry_on_transient(pipe.execute)
            self.logger.info("Redis sync complete.")
        else:
            self.logger.info("Nothing changed in Redis, skipping sync.")
