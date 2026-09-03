import os

LOG_LEVEL = "LOG_LEVEL"
USER_EMAIL = "USER_EMAIL"
SERVICE_ACCOUNT_EMAIL = "SERVICE_ACCOUNT_EMAIL"
ADMIN_EMAIL = "ADMIN_EMAIL"
REDIS_HOST = "REDIS_HOST"
REDIS_PORT = "REDIS_PORT"
REDIS_PASSWORD = "REDIS_PASSWORD"

# Used to initialize the Gerrit client.
GERRIT_URL = "GERRIT_URL"
GERRIT_USER = "GERRIT_USER"
GERRIT_HTTP_PASS = "GERRIT_HTTP_PASS"

# Used to create gerrit webhooks
GERRIT_WEBHOOK_REMOTE_NAME = "GERRIT_WEBHOOK_REMOTE_NAME"
GERRIT_WEBHOOK_TARGET_URL = "GERRIT_WEBHOOK_TARGET_URL"
GERRIT_WEBHOOK_EVENTS = "GERRIT_WEBHOOK_EVENTS"
GERRIT_WEBHOOK_PROJECT = "GERRIT_WEBHOOK_PROJECT"

AZURE_CLIENT_ID = "AZURE_CLIENT_ID"
AZURE_CLIENT_SECRET = "AZURE_CLIENT_SECRET"
AZURE_TENANT_ID = "AZURE_TENANT_ID"

JIRA_SERVER = "JIRA_SERVER"
JIRA_USER = "JIRA_USER"
JIRA_PASSWORD = "JIRA_PASSWORD"

MICROSOFT_ADMIN_LDAP = "MICROSOFT_ADMIN_LDAP"
MICROSOFT_USER_LDAP = "MICROSOFT_USER_LDAP"

LAUNCHDARKLY_SDK_KEY = "LAUNCHDARKLY_SDK_KEY"

PUBSUB_PROJECT_ID = "PUBSUB_PROJECT_ID"
MICROSOFT_SUBSCRIPTION_ID = "MICROSOFT_SUBSCRIPTION_ID"
GOOGLE_CHAT_SUBSCRIPTION_ID = "GOOGLE_CHAT_SUBSCRIPTION_ID"
GERRIT_SUBSCRIPTION_ID = "GERRIT_SUBSCRIPTION_ID"

DATABASE_URL = os.getenv("DATABASE_URL")

CF_TEAM_DOMAIN = os.getenv("CF_TEAM_DOMAIN")
CF_AUD_TAG = os.getenv("CF_AUD_TAG")
GOOGLE_AUDIENCE = os.getenv("GOOGLE_AUDIENCE")

# Comma-separated `unique_id`s of the service accounts allowed to authenticate
# with a Google identity token. Unset or empty parses to an empty set, which
# _verify_google refuses rather than falling back to the audience-only check.
GOOGLE_SERVICE_ACCOUNT_SUBS = frozenset(
    s.strip()
    for s in (os.getenv("GOOGLE_SERVICE_ACCOUNT_SUBS") or "").split(",")
    if s.strip()
)

TAILSCALE_PROXY = "TAILSCALE_PROXY"

MENTORSHIP_MENTOR_ONBOARDING_LINK = "MENTORSHIP_MENTOR_ONBOARDING_LINK"
MENTORSHIP_MENTEE_ONBOARDING_LINK = "MENTORSHIP_MENTEE_ONBOARDING_LINK"

RESUME_BUCKET = "RESUME_BUCKET"

# Google Calendar containers that app-created meetings live on, one per
# scenario. Each environment points at its own secondary calendar under
# USER_EMAIL, so a delete or a reschedule driven by one environment's data
# cannot reach another environment's events -- Calendar event ids are scoped
# per calendar, not globally.
#
# There is deliberately NO default and NO fallback to "primary": a missing
# value must fail at startup, because silently writing to the account's primary
# calendar is exactly the behaviour these variables exist to eliminate.
MENTORSHIP_CALENDAR_ID = "MENTORSHIP_CALENDAR_ID"
INTERVIEW_CALENDAR_ID = "INTERVIEW_CALENDAR_ID"

# Auth0 multi-IdP email OTP / account-link flow.
# Passwordless app drives the OTP send + verify; the M2M app holds Management
# API credentials for identity linking and app_metadata writes.
AUTH0_TENANT_DOMAIN = "AUTH0_TENANT_DOMAIN"
AUTH0_PASSWORDLESS_CLIENT_ID = "AUTH0_PASSWORDLESS_CLIENT_ID"
AUTH0_PASSWORDLESS_CLIENT_SECRET = "AUTH0_PASSWORDLESS_CLIENT_SECRET"
AUTH0_M2M_CLIENT_ID = "AUTH0_M2M_CLIENT_ID"
AUTH0_M2M_CLIENT_SECRET = "AUTH0_M2M_CLIENT_SECRET"
AUTH0_M2M_AUDIENCE = "AUTH0_M2M_AUDIENCE"

# HMAC secret signing the short-lived state JWT that ties an OTP verify back to
# the session that initiated it (CSRF guard).
EMAIL_OTP_STATE_JWT_SECRET = "EMAIL_OTP_STATE_JWT_SECRET"

# Company-wide Gmail account used to send and read candidate email, authorized
# once via OAuth2 refresh token (no in-app OAuth flow). The refresh token must
# carry the gmail.send and gmail.readonly scopes.
#
# The From address is per sending service, not per mailbox: one mailbox can send
# as several verified Send-As addresses, so each service gets its own variable
# (GMAIL_SENDER_RECRUITING today; a notification one when that feature sends
# mail). Each must be a real, receivable address (e.g. recruiting@circlecat.org)
# — never noreply@ — and must be registered and verified as a Send-As on the
# mailbox the refresh token belongs to, or Gmail silently rewrites the From to
# the mailbox owner. Every environment sets its own value so a test mail is
# recognisable as one; the code never knows which environment it is in.
#
# GmailClient is built eagerly at startup, so these must be set for the app to
# boot — but for LOCAL development you can use any placeholder values (e.g.
# "x"): they are only validated for presence and no network call is made until
# an email is actually sent or read. Real secrets live in the deployed secret
# store; you only need them locally if you are exercising the email feature.
GMAIL_CLIENT_ID = "GMAIL_CLIENT_ID"
GMAIL_CLIENT_SECRET = "GMAIL_CLIENT_SECRET"
GMAIL_REFRESH_TOKEN = "GMAIL_REFRESH_TOKEN"
GMAIL_SENDER_RECRUITING = "GMAIL_SENDER_RECRUITING"

# Per-service, per-environment From addresses. One mailbox, several Send-As
# aliases: recruiting correspondence and system notifications must be
# distinguishable in a recipient's inbox, and each environment sends from its
# own alias so a non-prod message can never look like a prod one.
GMAIL_SENDER_NOTIFICATION = "GMAIL_SENDER_NOTIFICATION"

# Fully qualified Pub/Sub topic (``projects/<p>/topics/<t>``) that
# publish_on_commit.install_publish_listener() publishes to once a
# notification-creating transaction commits. Holds the whole path, not just
# a bare topic id, so the app never has to know which project it is in --
# matching how GOOGLE_CHAT_SUBSCRIPTION_ID/GERRIT_SUBSCRIPTION_ID are ids
# combined with PUBSUB_PROJECT_ID elsewhere, this is its own env var instead
# because it is a topic, not a subscription, and is consumed as a complete
# path by a single call site rather than built up per-client.
NOTIFICATION_TOPIC = "NOTIFICATION_TOPIC"

# Comma-separated `sub` claims of the service accounts allowed to POST the
# notification delivery route. Absent does not raise at startup the way
# NOTIFICATION_TOPIC does: the route refuses every request instead, rather than
# crash-looping the whole API over one variable.
NOTIFICATION_PUSHER_SUBS = "NOTIFICATION_PUSHER_SUBS"


# SCORM training. The bucket holding course packages, the hostname they are
# served from, and the HMAC key signing the tokens in their URLs. All three are
# absent in local development; the code that needs them raises when used rather
# than at startup, so the app still boots.
TRAINING_BUCKET = "TRAINING_BUCKET"
TRAINING_CONTENT_HOST = "TRAINING_CONTENT_HOST"
TRAINING_TOKEN_SIGNING_KEY = "TRAINING_TOKEN_SIGNING_KEY"
