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
    AZURE_CLIENT_ID             = var.azure_client_id
    AZURE_TENANT_ID             = var.azure_tenant_id
    USER_EMAIL                  = "purrf@circlecat.org"
    ADMIN_EMAIL                 = "admin@circlecat.org"
    SERVICE_ACCOUNT_EMAIL       = "purrf-service@purrf-452300.iam.gserviceaccount.com"
    REDIS_HOST                  = upstash_redis_database.redis.endpoint
    REDIS_PORT                  = tostring(upstash_redis_database.redis.port)
    REDIS_PASSWORD              = upstash_redis_database.redis.password
    MICROSOFT_USER_LDAP         = "purrf"
    MICROSOFT_ADMIN_LDAP        = "catflirter"
    JIRA_SERVER                 = "http://jira-prod.tailcce60.ts.net"
    JIRA_USER                   = "purrf"
    JIRA_PASSWORD               = var.jira_password
    GERRIT_URL                  = "http://gerrit-prod.tailcce60.ts.net"
    GERRIT_USER                 = "wuyu"
    GERRIT_HTTP_PASS            = var.gerrit_http_pass
    DATABASE_URL                = local.app_sqlalchemy_async_url
    CF_TEAM_DOMAIN              = "ccat-dev.cloudflareaccess.com"
    CF_AUD_TAG                  = var.cf_aud_tag
    GOOGLE_AUDIENCE             = "purrf"
    PUBSUB_PROJECT_ID           = var.gcp_project_id
    MICROSOFT_SUBSCRIPTION_ID   = google_pubsub_subscription.subscriptions["chat-microsoft-events"].name
    GOOGLE_CHAT_SUBSCRIPTION_ID = google_pubsub_subscription.subscriptions["chat-google-events"].name
    GERRIT_SUBSCRIPTION_ID      = google_pubsub_subscription.subscriptions["gerrit-events"].name
    LAUNCHDARKLY_SDK_KEY        = var.ld_sdk_key
    TAILSCALE_PROXY             = var.tailscale_proxy
  }
}

resource "helm_release" "purrf_app" {
  name             = local.name_prefix
  chart            = "${path.module}/../../../helm/purrf"
  namespace        = local.name_prefix
  create_namespace = true
  atomic           = true
  cleanup_on_fail  = true
  timeout          = 300
  depends_on       = [kubernetes_secret.purrf_app]
  values = [
    yamlencode({

      fullnameOverride = local.name_prefix

      image = {
        repository = "us-docker.pkg.dev/k8s-dev-437501/purrf/purrf"
        tag        = var.image_tag
      }
      envFrom = [
        {
          secretRef = { name = local.name_prefix }
        }
      ]

      ingress = {
        enabled   = true
        className = var.ingress_class_name
        hosts = [
          {
            host = local.domains.api
            paths = [
              {
                path     = "/"
                pathType = "Prefix"
              }
            ]
          }
        ]
      }
    })
  ]
}

resource "google_service_account_iam_member" "purrf_service_wi" {
  service_account_id = "projects/purrf-452300/serviceAccounts/purrf-service@purrf-452300.iam.gserviceaccount.com"
  role               = "roles/iam.workloadIdentityUser"

  member = "serviceAccount:${var.k8s_project_id}.svc.id.goog[${local.name_prefix}/${local.name_prefix}]"
}
