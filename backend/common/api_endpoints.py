MY_PERMISSIONS = "/permissions/me"
EMAIL_MANAGEMENT_LIST_ENDPOINT = "/auth/emails"
EMAIL_MANAGEMENT_ADD_ENDPOINT = "/auth/emails/add"
EMAIL_MANAGEMENT_REMOVE_ENDPOINT = "/auth/emails/{email_id}"
EMAIL_MANAGEMENT_INITIATE_ENDPOINT = "/auth/emails/initiate"
EMAIL_MANAGEMENT_VERIFY_ENDPOINT = "/auth/emails/verify"
EMAIL_MANAGEMENT_SET_PRIMARY_INITIATE_ENDPOINT = (
    "/auth/emails/{email_id}/primary/initiate"
)
EMAIL_MANAGEMENT_SET_PRIMARY_CONFIRM_ENDPOINT = (
    "/auth/emails/{email_id}/primary/confirm"
)
EMAIL_MANAGEMENT_UNLINK_INITIATE_ENDPOINT = (
    "/auth/identities/{identity_id}/unlink/initiate"
)
EMAIL_MANAGEMENT_UNLINK_CONFIRM_ENDPOINT = (
    "/auth/identities/{identity_id}/unlink/confirm"
)
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

PUBSUB_SYNC_PULL_ENDPOINT = "/pubsub/sync"


MICROSOFT_LDAPS_ENDPOINT = "/microsoft/{status}/ldaps"
MICROSOFT_CHAT_COUNT_ENDPOINT = "/microsoft/chat/count"
MICROSOFT_CHAT_TOPICS_ENDPOINT = "/microsoft/chat/topics"

JIRA_PROJECTS_ENDPOINT = "/jira/projects"
JIRA_BRIEF_ENDPOINT = "/jira/brief"
JIRA_DETAIL_BATCH_ENDPOINT = "/jira/detail/batch"

GOOGLE_CALENDAR_LIST_ENDPOINT = "/calendar/calendars"
GOOGLE_CALENDAR_EVENTS_ENDPOINT = "/calendar/events"

GERRIT_STATS_ENDPOINT = "/gerrit/stats"
GERRIT_PROJECTS_ENDPOINT = "/gerrit/projects"

GOOGLE_CHAT_COUNT_ENDPOINT = "/google/chat/count"
GOOGLE_CHAT_SPACES_ENDPOINT = "/google/chat/spaces"

SUMMARY_ENDPOINT = "/summary"
MY_SUMMARY_ENDPOINT = "/summary/me"

MY_PROFILE_ENDPOINT = "/profiles/me"

MENTORSHIP_ROUNDS_ENDPOINT = "/mentorship/rounds"
MENTORSHIP_ROUNDS_REGISTRATION_ENDPOINT = "/mentorship/rounds/{round_id}/registration"
MENTORSHIP_MATCH_RESULT_ENDPOINT = "/mentorship/rounds/{round_id}/matches"
MENTORSHIP_PARTNERS_ENDPOINT = "/mentorship/partners/me"
MENTORSHIP_MEETINGS_ENDPOINT = "/mentorship/v1/meetings"
MENTORSHIP_MEETING_V2_ENDPOINT = "/mentorship/v2/meetings"
MENTORSHIP_MEETING_V2_SINGLE_ENDPOINT = "/mentorship/v2/meetings/{meeting_id}"
MENTORSHIP_MEETING_V2_BATCH_DELETE_ENDPOINT = "/mentorship/v2/meetings/batch-delete"
MEET_ATTENDANCE_SYNC_ENDPOINT = "/mentorship/v2/meetings/attendance/sync"
MENTORSHIP_ROUNDS_FEEDBACK_ENDPOINT = "/mentorship/rounds/{round_id}/feedback"
MENTORSHIP_ADMIN_PARTICIPANTS = "/mentorship/admin/participants"
MENTORSHIP_ADMIN_PAIRS_MEETINGS = "/mentorship/admin/pairs/{pair_id}/meetings"

ADMIN_PERMISSIONS_ENDPOINT = "/admin/permissions"
ADMIN_USERS_ENDPOINT = "/admin/users"
ADMIN_USER_PERMISSIONS_ENDPOINT = "/admin/users/{user_id}/permissions"
ADMIN_PERMISSION_USERS_ENDPOINT = "/admin/permissions/{permission_name}/users"
ADMIN_AUDIT_PERMISSION_CHANGES_ENDPOINT = "/admin/audit/permission-changes"
ADMIN_USER_GRANT_PERMISSIONS_ENDPOINT = "/admin/users/{user_id}/permissions/grant"
ADMIN_USER_REVOKE_PERMISSIONS_ENDPOINT = "/admin/users/{user_id}/permissions/revoke"
ADMIN_USER_SUPER_ADMIN_ENDPOINT = "/admin/users/{user_id}/super-admin"
RECRUITING_JOBS_ENDPOINT = "/recruiting/jobs"
RECRUITING_JOB_ENDPOINT = "/recruiting/jobs/{job_id}"
RECRUITING_JOB_SUBMIT_ENDPOINT = "/recruiting/jobs/{job_id}/submit"
RECRUITING_JOB_REQUEST_CLOSE_ENDPOINT = "/recruiting/jobs/{job_id}/request-close"
RECRUITING_JOB_REQUEST_REOPEN_ENDPOINT = "/recruiting/jobs/{job_id}/request-reopen"
RECRUITING_JOB_DISCARD_PENDING_EDIT_ENDPOINT = (
    "/recruiting/jobs/{job_id}/discard-pending-edit"
)
RECRUITING_APPROVERS_ENDPOINT = "/recruiting/approvers"
RECRUITING_REVIEWS_ENDPOINT = "/recruiting/reviews"
RECRUITING_REVIEW_ENDPOINT = "/recruiting/reviews/{review_id}"
RECRUITING_INTERVIEW_POOL_ENDPOINT = "/recruiting/interview-pool"
RECRUITING_JOB_OWNERS_ENDPOINT = "/recruiting/job-owners"
RECRUITING_JOB_ACTIVITY_ENDPOINT = "/recruiting/jobs/{job_id}/activity"
RECRUITING_PUBLIC_JOB_ENDPOINT = "/recruiting/public/jobs/{job_id}"
RECRUITING_PUBLIC_JOBS_ENDPOINT = "/recruiting/public/jobs"
RECRUITING_RESUMES_ENDPOINT = "/recruiting/resumes"
RECRUITING_APPLICATIONS_ENDPOINT = "/recruiting/applications"
RECRUITING_APPLICATION_ENDPOINT = "/recruiting/applications/{application_id}"
RECRUITING_APPLICATIONS_MINE_ENDPOINT = "/recruiting/applications/mine"
RECRUITING_MY_APPLICATIONS_ENDPOINT = "/recruiting/my-applications"
RECRUITING_BOARD_JOBS_ENDPOINT = "/recruiting/board/jobs"
RECRUITING_JOB_BOARD_ENDPOINT = "/recruiting/jobs/{job_id}/board"
RECRUITING_APPLICATION_STAGE_ENDPOINT = (
    "/recruiting/applications/{application_id}/stage"
)
RECRUITING_APPLICATION_SUB_STATUS_ENDPOINT = (
    "/recruiting/applications/{application_id}/sub-status"
)
RECRUITING_APPLICATION_ASSIGNMENT_ENDPOINT = (
    "/recruiting/applications/{application_id}/assignment"
)
RECRUITING_APPLICATION_ROUND_ENDPOINT = (
    "/recruiting/applications/{application_id}/round"
)
RECRUITING_BLACKLIST_ENDPOINT = "/recruiting/blacklist"
RECRUITING_BLACKLIST_UNBLOCK_ENDPOINT = "/recruiting/blacklist/{user_id}"
RECRUITING_APPLICATION_RESUME_ENDPOINT = (
    "/recruiting/applications/{application_id}/resume"
)
RECRUITING_APPLICATION_EVALUATION_ENDPOINT = (
    "/recruiting/applications/{application_id}/evaluation"
)
RECRUITING_EVALUATIONS_MINE_ENDPOINT = "/recruiting/evaluations/mine"
RECRUITING_APPLICATION_EVALUATIONS_ENDPOINT = (
    "/recruiting/applications/{application_id}/evaluations"
)
RECRUITING_APPLICATION_ACTIVITY_ENDPOINT = (
    "/recruiting/applications/{application_id}/activity"
)
RECRUITING_APPLICATION_OTHER_APPLICATIONS_ENDPOINT = (
    "/recruiting/applications/{application_id}/other-applications"
)
RECRUITING_APPLICATION_COMMENTS_ENDPOINT = (
    "/recruiting/applications/{application_id}/comments"
)
RECRUITING_AUDIT_OVERVIEW_ENDPOINT = "/recruiting/audit/overview"
RECRUITING_APPLICATION_MENTIONABLE_USERS_ENDPOINT = (
    "/recruiting/applications/{application_id}/mentionable-users"
)
RECRUITING_NOTIFICATIONS_ENDPOINT = "/recruiting/notifications"
RECRUITING_NOTIFICATION_READ_ENDPOINT = (
    "/recruiting/notifications/{notification_id}/read"
)
RECRUITING_NOTIFICATIONS_READ_ALL_ENDPOINT = "/recruiting/notifications/read-all"
