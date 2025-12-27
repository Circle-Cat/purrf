MY_ROLES = "/roles/me"
GOOGLE_CHAT_SUBSCRIBE_ENDPOINT = "/google/chat/spaces/subscribe"
MICROSOFT_CHAT_SUBSCRIBE_ENDPOINT = "/microsoft/chat/subscribe"

MICROSOFT_BACKFILL_LDAPS_ENDPOINT = "/microsoft/backfill/ldaps"
MICROSOFT_BACKFILL_CHAT_MESSAGES_ENDPOINT = "/microsoft/backfill/chat/messages/{chatId}"

JIRA_SYNC_PROJECTS_ENDPOINT = "/jira/project"
JIRA_BACKFILL_ISSUES_ENDPOINT = "/jira/backfill"
JIRA_UPDATE_ISSUES_ENDPOINT = "/jira/update"

GOOGLE_CALENDAR_PULL_HISTORY_ENDPOINT = "/google/calendar/history/pull"
GOOGLE_CHAT_SYNC_HISTORY_MESSAGES_ENDPOINT = "/google/chat/spaces/messages"

GERRIT_BACKFILL_CHANGES_ENDPOINT = "/gerrit/backfill"
GERRIT_BACKFILL_PROJECTS_ENDPOINT = "/gerrit/projects/backfill"

MICROSOFT_PULL_ENDPOINT = "/microsoft/pull/{project_id}/{subscription_id}"
GOOGLE_CHAT_PULL_ENDPOINT = "/google/chat/pull/{project_id}/{subscription_id}"
GERRIT_PULL_ENDPOINT = "/gerrit/pull/{project_id}/{subscription_id}"
PUBSUB_STATUS_ENDPOINT = "/pubsub/pull/status/{project_id}/{subscription_id}"
PUBSUB_STOP_ENDPOINT = "/pubsub/pull/{project_id}/{subscription_id}"
