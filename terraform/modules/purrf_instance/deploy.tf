resource "kubernetes_namespace" "purrf_app" {
  metadata {
    name = local.name_prefix
  }
}

resource "kubernetes_secret" "purrf_app" {
  metadata {
    name      = local.name_prefix
    namespace = kubernetes_namespace.purrf_app.metadata[0].name
  }

  data = {
    AZURE_CLIENT_ID                   = var.azure_client_id
    AZURE_TENANT_ID                   = var.azure_tenant_id
    USER_EMAIL                        = "purrf@circlecat.org"
    ADMIN_EMAIL                       = "admin@circlecat.org"
    SERVICE_ACCOUNT_EMAIL             = "purrf-service@purrf-452300.iam.gserviceaccount.com"
    REDIS_HOST                        = upstash_redis_database.redis.endpoint
    REDIS_PORT                        = tostring(upstash_redis_database.redis.port)
    REDIS_PASSWORD                    = upstash_redis_database.redis.password
    MICROSOFT_USER_LDAP               = "purrf"
    MICROSOFT_ADMIN_LDAP              = "catflirter"
    JIRA_SERVER                       = "http://jira-prod.tailcce60.ts.net"
    JIRA_USER                         = "purrf"
    JIRA_PASSWORD                     = var.jira_password
    GERRIT_URL                        = "http://gerrit-prod.tailcce60.ts.net"
    GERRIT_USER                       = "wuyu"
    GERRIT_HTTP_PASS                  = var.gerrit_http_pass
    DATABASE_URL                      = local.app_sqlalchemy_async_url
    CF_TEAM_DOMAIN                    = "ccat-dev.cloudflareaccess.com"
    CF_AUD_TAG                        = var.cf_aud_tag
    GOOGLE_AUDIENCE                   = "purrf"
    PUBSUB_PROJECT_ID                 = var.gcp_project_id
    MICROSOFT_SUBSCRIPTION_ID         = google_pubsub_subscription.subscriptions["chat-microsoft-events"].name
    GOOGLE_CHAT_SUBSCRIPTION_ID       = google_pubsub_subscription.subscriptions["chat-google-events"].name
    GERRIT_SUBSCRIPTION_ID            = google_pubsub_subscription.subscriptions["gerrit-events"].name
    LAUNCHDARKLY_SDK_KEY              = var.ld_sdk_key
    TAILSCALE_PROXY                   = var.tailscale_proxy
    MENTORSHIP_MENTOR_ONBOARDING_LINK = "https://circle-cat-inc-3811.reach360.com/share/course/3d9db106-543a-4d4d-98c2-7edee343d53f"
    MENTORSHIP_MENTEE_ONBOARDING_LINK = "https://learn.circlecat.cn/course/view.php?id=16"
    RESUME_BUCKET                     = google_storage_bucket.resumes.name

    # Auth0 multi-IdP email OTP / account-link flow, sourced straight from the
    # Auth0 resources in auth0.tf -- no manual values to supply.
    AUTH0_TENANT_DOMAIN              = data.auth0_tenant.current.domain
    AUTH0_PASSWORDLESS_CLIENT_ID     = auth0_client.purrf_auth0.client_id
    AUTH0_PASSWORDLESS_CLIENT_SECRET = auth0_client_credentials.purrf_auth0.client_secret
    AUTH0_M2M_CLIENT_ID              = auth0_client.link_action_m2m.client_id
    AUTH0_M2M_CLIENT_SECRET          = auth0_client_credentials.link_action_m2m.client_secret
    AUTH0_M2M_AUDIENCE               = "https://${data.auth0_tenant.current.domain}/api/v2/"

    # App-internal HMAC secret signing the OTP state JWT (CSRF guard); generated
    # here, not an Auth0 value.
    EMAIL_OTP_STATE_JWT_SECRET = random_password.email_otp_state_secret.result

    # Gmail API integration for recruiting candidate emails. Client credentials
    # come from the purrf-auth GCP project; the refresh token is minted once via
    # interactive consent (not Terraform-managed). test/staging point at a test
    # mailbox, prod at the real sender -- all four supplied per-env via TF_VAR.
    GMAIL_CLIENT_ID      = var.gmail_client_id
    GMAIL_CLIENT_SECRET  = var.gmail_client_secret
    GMAIL_REFRESH_TOKEN  = var.gmail_refresh_token
    GMAIL_SENDER_ADDRESS = var.gmail_sender_address
  }
}

# HMAC key for the short-lived OTP state JWT (EMAIL_OTP_STATE_JWT_SECRET).
# Generated and held in Terraform state so it is stable across applies; rotate
# by tainting this resource.
resource "random_password" "email_otp_state_secret" {
  length  = 64
  special = false
}

resource "google_service_account_iam_member" "purrf_service_wi" {
  service_account_id = "projects/purrf-452300/serviceAccounts/purrf-service@purrf-452300.iam.gserviceaccount.com"
  role               = "roles/iam.workloadIdentityUser"

  member = "serviceAccount:${var.k8s_project_id}.svc.id.goog[${local.name_prefix}/${local.name_prefix}]"
}
