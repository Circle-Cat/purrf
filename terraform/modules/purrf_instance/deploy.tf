resource "helm_release" "purrf_app" {
  name             = local.name_prefix
  chart            = "${path.module}/../../../helm/purrf"
  namespace        = local.name_prefix
  create_namespace = true
  atomic           = true
  cleanup_on_fail  = true
  timeout          = 300
  values = [
    yamlencode({

      fullnameOverride = local.name_prefix

      image = {
        repository = "us-docker.pkg.dev/k8s-dev-437501/purrf/purrf"
        tag        = var.image_tag
      }
      env = [
        { name = "AZURE_CLIENT_ID", value = "8f3f85f2-be71-4ed5-95e8-3c777f4c6e13" },
        { name = "AZURE_TENANT_ID", value = "08502fd6-503a-4dfd-85b7-f13b141dc0c4" },
        { name = "USER_EMAIL", value = "purrf@circlecat.org" },
        { name = "ADMIN_EMAIL", value = "admin@circlecat.org" },
        { name = "SERVICE_ACCOUNT_EMAIL", value = "purrf-service@purrf-452300.iam.gserviceaccount.com" },
        { name = "REDIS_HOST", value = upstash_redis_database.redis.endpoint },
        { name = "REDIS_PORT", value = tostring(upstash_redis_database.redis.port) },
        { name = "REDIS_PASSWORD", value = upstash_redis_database.redis.password },
        { name = "MICROSOFT_USER_LDAP", value = "purrf" },
        { name = "MICROSOFT_ADMIN_LDAP", value = "catflirter" },
        { name = "JIRA_SERVER", value = "http://jira-prod.tailcce60.ts.net" },
        { name = "JIRA_USER", value = "purrf" },
        { name = "JIRA_PASSWORD", value = var.jira_password },
        { name = "GERRIT_URL", value = "http://gerrit-prod.tailcce60.ts.net" },
        { name = "GERRIT_USER", value = "wuyu" },
        { name = "GERRIT_HTTP_PASS", value = var.gerrit_http_pass },
        { name = "DATABASE_URL", value = local.app_sqlalchemy_async_url },
        { name = "CF_TEAM_DOMAIN", value = "ccat-dev.cloudflareaccess.com" },
        { name = "CF_AUD_TAG", value = var.cf_aud_tag },
        { name = "GOOGLE_AUDIENCE", value = "purrf" }
      ]

      ingress = {
        enabled = true
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

  member = "serviceAccount:circlecat.svc.id.goog[${local.name_prefix}/${local.name_prefix}]"
}
