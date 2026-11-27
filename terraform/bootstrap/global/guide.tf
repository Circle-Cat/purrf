# Purrf Work Guide: a Starlight site built from Circle-Cat/purrf-guide and
# served at guide.purrf.io. Only the people in purrf_guide_readers can open it;
# the link inside Purrf is shown by the LaunchDarkly flag work-guide.

locals {
  purrf_guide_host = "guide.purrf.io"

  # Who can open the guide. Keep in step with the work-guide flag's email list.
  # GitHub OAuth App "Purrf Guide Editor" (Circle-Cat org): sign-in for the
  # Decap editor at guide.purrf.io/admin. Its callback is /api/callback.
  purrf_guide_github_client_id = "Ov23liCiPsPjsBNVywiS"

  purrf_guide_readers = [
    "yuji@circlecat.org",
    "jasmine@circlecat.org",
    "daisyisadaisy@circlecat.org",
    "admin@circlecat.org",
    "jxie@circlecat.org",
    "wuyu@circlecat.org",
  ]
}

# The OAuth App's client secret. No default on purpose: a plan or apply run
# without it stops with an error instead of blanking the secret on Pages.
#   export TF_VAR_purrf_guide_github_client_secret='<client secret>'
# The value is copied into the Pages project, so it also sits in this root's
# state.
variable "purrf_guide_github_client_secret" {
  type      = string
  sensitive = true
}

resource "cloudflare_pages_project" "purrf_guide" {
  account_id        = local.cloudflare_account_id
  name              = "purrf-guide"
  production_branch = "main"
  build_config = {
    build_command   = "npm run build"
    destination_dir = "dist"
    root_dir        = ""
  }
  source = {
    type = "github"
    config = {
      owner                          = "Circle-Cat"
      repo_name                      = "purrf-guide"
      production_branch              = "main"
      production_deployments_enabled = true
      pr_comments_enabled            = true
      preview_deployment_setting     = "all"
    }
  }
  deployment_configs = {
    preview = {
      always_use_latest_compatibility_date = false
      build_image_major_version            = 3
      compatibility_date                   = "2025-09-18"
      fail_open                            = true
    }
    # Only production signs in to the editor: GitHub accepts the one callback
    # on guide.purrf.io, so preview hosts get no OAuth settings.
    production = {
      always_use_latest_compatibility_date = false
      build_image_major_version            = 3
      compatibility_date                   = "2025-09-18"
      fail_open                            = true
      env_vars = {
        "GITHUB_CLIENT_ID" = {
          type  = "plain_text"
          value = local.purrf_guide_github_client_id
        }
        "GITHUB_CLIENT_SECRET" = {
          type  = "secret_text"
          value = var.purrf_guide_github_client_secret
        }
      }
    }
  }
}

resource "cloudflare_pages_domain" "purrf_guide" {
  account_id   = local.cloudflare_account_id
  project_name = cloudflare_pages_project.purrf_guide.name
  name         = local.purrf_guide_host
}

resource "cloudflare_dns_record" "purrf_guide" {
  zone_id = local.zone_id
  name    = "guide"
  type    = "CNAME"
  content = cloudflare_pages_project.purrf_guide.subdomain
  proxied = true
  ttl     = 1
  lifecycle {
    ignore_changes = [
      comment,
    ]
  }
}

# Readers sign in the same way as on purrf.io (prod Auth0). The Auth0 IdP maps
# the Access email to the "aud" claim, so the list is matched on the OIDC
# "email" claim instead of Access's email rule.
resource "cloudflare_zero_trust_access_policy" "purrf_guide_readers" {
  account_id = local.cloudflare_account_id
  name       = "Purrf guide readers"
  decision   = "allow"
  include = [
    for email in local.purrf_guide_readers : {
      oidc = {
        identity_provider_id = cloudflare_zero_trust_access_identity_provider.mentorship_login_prod.id
        claim_name           = "email"
        claim_value          = email
      }
    }
  ]

  # Provider 5.29 fails to update this policy in place (Cloudflare answers
  # 12130 "unrecognized policy decision"), so a changed list is applied with
  # -replace. The new policy has to exist before the application can point at
  # it and the old one can go.
  lifecycle {
    create_before_destroy = true
  }
}

resource "cloudflare_zero_trust_access_application" "purrf_guide" {
  account_id = local.cloudflare_account_id
  name       = "purrf-guide"
  domain     = local.purrf_guide_host
  type       = "self_hosted"
  # The pages.dev hosts (production and every preview) serve the same files, so
  # they sit behind Access too.
  destinations = [
    { type = "public", uri = local.purrf_guide_host },
    { type = "public", uri = cloudflare_pages_project.purrf_guide.subdomain },
    { type = "public", uri = "*.${cloudflare_pages_project.purrf_guide.subdomain}" },
  ]
  allowed_idps              = [cloudflare_zero_trust_access_identity_provider.mentorship_login_prod.id]
  auto_redirect_to_identity = true
  session_duration          = "24h"
  app_launcher_visible      = false
  policies = [
    {
      id         = cloudflare_zero_trust_access_policy.purrf_guide_readers.id
      precedence = 1
    },
  ]
}
