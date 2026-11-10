from datetime import datetime, timezone

from backend.common.constants import (
    MICROSOFT_TEAMS_CHAT_MESSAGES_SUBSCRIPTION_RESOURCE,
    SINGLE_GOOGLE_CHAT_EVENT_TYPES,
)

MONITOR_EVENT = "subscription.status"
STATUS_OK = "ok"
STATUS_MISSING = "missing"
STATUS_EXPIRED = "expired"
GOOGLE_CHAT_ACTIVE = "ACTIVE"
GOOGLE_CHAT_TARGET_PREFIX = "//chat.googleapis.com/"


class ChatSubscriptionCheckService:
    """Compares the chat subscriptions this environment holds with the ones it should.

    Neither kind fails loudly when it dies: Graph removes a Teams subscription
    with only a lifecycle warning, and a suspended Google Chat subscription
    stops receiving the reminders that renew it. Each expected chat gets one
    ``subscription.status`` log line, which Cloud Monitoring alerts on.
    """

    def __init__(
        self,
        logger,
        microsoft_service,
        google_workspaceevents_client,
        retry_utils,
        expected_teams_chats,
        expected_google_chat_spaces,
        teams_notification_url,
        google_chat_events_topic,
    ):
        """
        Args:
            logger: Application logger.
            microsoft_service (MicrosoftService): Lists Graph subscriptions.
            google_workspaceevents_client: Workspace Events API client.
            retry_utils (RetryUtils): Retries transient API errors.
            expected_teams_chats (list[str]): Teams chat ids that should be subscribed.
            expected_google_chat_spaces (list[str]): Google Chat spaces, as
                ``spaces/<id>``, that should be subscribed.
            teams_notification_url (str): Where this environment's Teams
                subscriptions deliver.
            google_chat_events_topic (str): Pub/Sub topic, as
                ``projects/<p>/topics/<t>``, this environment's Google Chat
                subscriptions publish to.
        """
        self.logger = logger
        self.microsoft_service = microsoft_service
        self.google_workspaceevents_client = google_workspaceevents_client
        self.retry_utils = retry_utils
        self.expected_teams_chats = expected_teams_chats
        self.expected_google_chat_spaces = expected_google_chat_spaces
        self.teams_notification_url = teams_notification_url
        self.google_chat_events_topic = google_chat_events_topic

    async def check(self) -> dict:
        """Log the status of every expected subscription and return a summary.

        A failing API call propagates, so the calling job fails rather than
        reporting chats as missing.

        Returns:
            dict: ``{"teams": [...], "googleChat": [...]}``, each item
            ``{"target", "status", "expiresAt"}``.
        """
        teams = await self._check_teams() if self.expected_teams_chats else []
        google_chat = (
            self._check_google_chat() if self.expected_google_chat_spaces else []
        )
        for provider, results in (("teams", teams), ("google_chat", google_chat)):
            for result in results:
                self._log(provider, result)
        return {"teams": teams, "googleChat": google_chat}

    async def _check_teams(self) -> list[dict]:
        subscriptions = await self.microsoft_service.list_all_subscriptions()
        now = datetime.now(timezone.utc)
        results = []
        for chat_id in self.expected_teams_chats:
            resource = MICROSOFT_TEAMS_CHAT_MESSAGES_SUBSCRIPTION_RESOURCE.format(
                chat_id=chat_id
            )
            ours = [
                s
                for s in subscriptions
                if s.resource == resource
                and s.notification_url == self.teams_notification_url
            ]
            if not ours:
                results.append(_result(chat_id, STATUS_MISSING, None))
                continue
            expires_at = max(s.expiration_date_time for s in ours)
            status = STATUS_OK if expires_at > now else STATUS_EXPIRED
            results.append(_result(chat_id, status, expires_at.isoformat()))
        return results

    def _check_google_chat(self) -> list[dict]:
        subscriptions = self._list_google_chat_subscriptions()
        results = []
        for space in self.expected_google_chat_spaces:
            ours = [
                s
                for s in subscriptions
                if s.get("targetResource") == GOOGLE_CHAT_TARGET_PREFIX + space
                and s.get("notificationEndpoint", {}).get("pubsubTopic")
                == self.google_chat_events_topic
            ]
            if not ours:
                results.append(_result(space, STATUS_MISSING, None))
                continue
            active = [s for s in ours if s.get("state") == GOOGLE_CHAT_ACTIVE]
            chosen = active[0] if active else ours[0]
            # Not ACTIVE is reported as the state itself, e.g. "suspended",
            # with Google's reason appended when it gives one.
            status = (
                STATUS_OK
                if active
                else "_".join(
                    filter(
                        None,
                        [
                            chosen.get("state", "unknown").lower(),
                            chosen.get("suspensionReason", "").lower(),
                        ],
                    )
                )
            )
            results.append(_result(space, status, chosen.get("expireTime")))
        return results

    def _list_google_chat_subscriptions(self) -> list[dict]:
        # The API requires an event-type filter; every subscription Purrf makes
        # carries the message-created type.
        subscriptions = []
        page_token = None
        while True:
            request = self.google_workspaceevents_client.subscriptions().list(
                filter=f'event_types:"{SINGLE_GOOGLE_CHAT_EVENT_TYPES[0]}"',
                pageToken=page_token,
            )
            response = self.retry_utils.get_retry_on_transient(request.execute)
            subscriptions.extend(response.get("subscriptions", []))
            page_token = response.get("nextPageToken")
            if not page_token:
                return subscriptions

    def _log(self, provider: str, result: dict):
        log = self.logger.info if result["status"] == STATUS_OK else self.logger.warning
        log(
            "Chat subscription %s %s: %s",
            provider,
            result["target"],
            result["status"],
            extra={
                "monitor_event": MONITOR_EVENT,
                "provider": provider,
                "target": result["target"],
                "status": result["status"],
                "expires_at": result["expiresAt"],
            },
        )


def _result(target: str, status: str, expires_at: str | None) -> dict:
    return {"target": target, "status": status, "expiresAt": expires_at}
