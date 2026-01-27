resource "cloudflare_ruleset" "cors_headers" {
  zone_id = local.zone_id
  name    = "default"
  kind    = "zone"
  phase   = "http_response_headers_transform"

  rules = [
    for env in local.environments : {
      action      = "rewrite"
      description = "CORS Header for Purrf ${env.name}"
      enabled     = true

      expression = "(http.host eq \"${env.api_host}\" and http.request.uri.path wildcard r\"/api/*\")"

      action_parameters = {
        headers = {
          "Access-Control-Allow-Origin" = {
            operation = "set"
            value     = "https://${env.origin_web}"
          }
          "Access-Control-Allow-Methods" = {
            operation = "set"
            value     = "GET, POST, OPTIONS, DELETE, PUT, PATCH"
          }
          "Access-Control-Allow-Headers" = {
            operation = "set"
            value     = "Content-Type, Authorization"
          }
          "Access-Control-Allow-Credentials" = {
            operation = "set"
            value     = "true"
          }
        }
      }
    }
  ]
}

resource "cloudflare_ruleset" "global_waf" {
  zone_id = local.zone_id
  name    = "Allow Microsoft and Gerrit IPs only"
  kind    = "zone"
  phase   = "http_request_firewall_custom"

  rules = [
    for key, env in local.environments : {
      action = "block"
      expression = format("(http.host eq \"%s\") and not ip.src in {%s}",
        env.cf_host,
      join(" ", local.webhook_ips))
      description = "IP Restriction for ${env.name}"
      enabled     = true
    }
  ]
}

# Get purrf project details
data "google_project" "main_gcp_project_data" {
  project_id = var.main_gcp_project_id
}

# Get circlecat project details
data "google_project" "circlecat_project_data" {
  project_id = var.circlecat_project_id
}


# Define an Access Context Manager policy for VPC Service Controls perimeter
resource "google_access_context_manager_access_policy" "purrf_internal" {
  parent = "organizations/${var.organization_id}"
  scopes = ["projects/${data.google_project.main_gcp_project_data.number}"]
  title  = "purrf_internal"
}

# Create a VPC Service Controls perimeter to protect the Purrf project
resource "google_access_context_manager_service_perimeter" "purrf_primary_perimeter" {
  description               = "Perimeter covering the Purrf project and Circlecat's main network."
  name                      = "accessPolicies/${google_access_context_manager_access_policy.purrf_internal.name}/servicePerimeters/purrf_primary_perimeter"
  parent                    = "accessPolicies/${google_access_context_manager_access_policy.purrf_internal.name}"
  perimeter_type            = "PERIMETER_TYPE_REGULAR"
  title                     = "purrf-primary-perimeter"
  use_explicit_dry_run_spec = false
  status {
    access_levels = []
    resources = [
      "projects/${data.google_project.main_gcp_project_data.number}",
    ]
    restricted_services = ["cloudfunctions.googleapis.com"]

    # Egress policy: allow perimeter resources to call any service
    egress_policies {
      egress_from {
        identities         = []
        identity_type      = "ANY_IDENTITY"
        source_restriction = null
      }
      egress_to {
        external_resources = []
        resources          = ["*"]
        operations {
          service_name = "*"
        }
      }
    }

    # Ingress policy: allow traffic from Circlecat's main VPC network
    ingress_policies {
      ingress_from {
        identities    = []
        identity_type = "ANY_IDENTITY"
        sources {
          access_level = null
          resource     = "//compute.googleapis.com/${data.google_project.circlecat_project_data.id}/global/networks/main"
        }
      }
      ingress_to {
        resources = ["*"]
        operations {
          service_name = "*"
        }
      }
    }

    # Ingress policy: allow traffic from a specific user
    ingress_policies {
      ingress_from {
        identities    = ["user:yuji@circlecat.org"]
        identity_type = null
        sources {
          access_level = "*"
          resource     = null
        }
      }
      ingress_to {
        resources = ["*"]
        operations {
          service_name = "*"
        }
      }
    }
  }
}

data "terraform_remote_state" "test_env" {
  backend = "gcs"
  config = {
    bucket = "purrf-terraform-state"
    prefix = "test"
  }
}

data "terraform_remote_state" "prod_env" {
  backend = "gcs"
  config = {
    bucket = "purrf-terraform-state"
    prefix = "prod"
  }
}

resource "cloudflare_pages_project" "purrf_production" {
  account_id        = local.cloudflare_account_id
  name              = "purrf"
  production_branch = "prod"
  build_config = {
    build_command = <<EOF
    go run github.com/bazelbuild/bazelisk@latest build //frontend:dist \
      --action_env=VITE_API_BASE_URL=$VITE_API_BASE_URL \
      --action_env=VITE_AUTH0_CLIENT_ID=$VITE_AUTH0_CLIENT_ID \
      --action_env=VITE_AUTH0_DOMAIN=$VITE_AUTH0_DOMAIN \
      --action_env=VITE_CF_ACCESS_TENANT_DOMAIN=$VITE_CF_ACCESS_TENANT_DOMAIN
    EOF

    destination_dir = "bazel-bin/frontend/dist"
    root_dir        = ""
  }
  source = {
    type = "github"
    config = {
      owner                          = "Circle-Cat"
      repo_name                      = "purrf"
      production_branch              = "prod"
      production_deployments_enabled = true
      pr_comments_enabled            = true
      preview_deployment_setting     = "custom"
      preview_branch_includes = [
        "main",
      ]
      path_includes = [
        "frontend/*",
      ]
    }
  }
  deployment_configs = {
    preview = {
      always_use_latest_compatibility_date = false
      build_image_major_version            = 3
      compatibility_date                   = "2025-09-18"
      env_vars = {
        "VITE_API_BASE_URL" = {
          type  = "plain_text"
          value = "https://${local.environments.test.api_host}"

        }
        "VITE_AUTH0_CLIENT_ID" = {
          type  = "plain_text"
          value = data.terraform_remote_state.test_env.outputs.auth0_client_id
        }
        "VITE_AUTH0_DOMAIN" = {
          type  = "plain_text"
          value = "dev-6mz4iysn6gfkcudu.us.auth0.com"
        }
        "VITE_CF_ACCESS_TENANT_DOMAIN" = {
          type  = "plain_text"
          value = "ccat-dev.cloudflareaccess.com"
        }
        "SKIP_DEPENDENCY_INSTALL" = {
          type  = "plain_text"
          value = "true"
        }
      }
      fail_open = true
    }
    production = {
      always_use_latest_compatibility_date = false
      build_image_major_version            = 3
      compatibility_date                   = "2025-09-18"
      env_vars = {
        "VITE_API_BASE_URL" = {
          type  = "plain_text"
          value = "https://${local.environments.prod.api_host}"

        }
        "VITE_AUTH0_CLIENT_ID" = {
          type  = "plain_text"
          value = data.terraform_remote_state.prod_env.outputs.auth0_client_id
        }
        "VITE_AUTH0_DOMAIN" = {
          type  = "plain_text"
          value = "dev-6mz4iysn6gfkcudu.us.auth0.com"
        }
        "VITE_CF_ACCESS_TENANT_DOMAIN" = {
          type  = "plain_text"
          value = "ccat-dev.cloudflareaccess.com"
        }
        "SKIP_DEPENDENCY_INSTALL" = {
          type  = "plain_text"
          value = "true"
        }
      }
      fail_open = true
    }
  }
}

resource "cloudflare_pages_domain" "purrf_io_prod" {
  account_id   = local.cloudflare_account_id
  project_name = "purrf"
  name         = "purrf.io"
}

resource "cloudflare_pages_domain" "purrf_io_test" {
  account_id   = local.cloudflare_account_id
  project_name = "purrf"
  name         = "test.purrf.io"
}

resource "cloudflare_dns_record" "api_prod" {
  zone_id = local.zone_id
  name    = "api"
  type    = "CNAME"
  content = "0a108bed-55ea-4c18-88b3-fd9bb68105ae.cfargotunnel.com"
  proxied = true
  ttl     = 1
  lifecycle {
    ignore_changes = [
      comment,
    ]
  }
}

resource "cloudflare_dns_record" "cf_prod" {
  zone_id = local.zone_id
  name    = "cf"
  type    = "CNAME"
  content = "dd604706-9340-414a-8afb-2bf673049bbd.cfargotunnel.com"
  proxied = true
  ttl     = 1
  lifecycle {
    ignore_changes = [
      comment,
    ]
  }
}

resource "cloudflare_dns_record" "root_prod" {
  zone_id = local.zone_id
  name    = "@"
  type    = "CNAME"
  content = "purrf.pages.dev"
  proxied = true
  ttl     = 1
  lifecycle {
    ignore_changes = [
      comment,
    ]
  }
}

resource "cloudflare_dns_record" "api_test" {
  zone_id = local.zone_id
  name    = "test-api"
  type    = "CNAME"
  content = "0a108bed-55ea-4c18-88b3-fd9bb68105ae.cfargotunnel.com"
  proxied = true
  ttl     = 1
  lifecycle {
    ignore_changes = [
      comment,
    ]
  }
}

resource "cloudflare_dns_record" "cf_test" {
  zone_id = local.zone_id
  name    = "test-cf"
  type    = "CNAME"
  content = "dd604706-9340-414a-8afb-2bf673049bbd.cfargotunnel.com"
  proxied = true
  ttl     = 1
  lifecycle {
    ignore_changes = [
      comment,
    ]
  }
}

resource "cloudflare_dns_record" "root_test" {
  zone_id = local.zone_id
  name    = "test"
  type    = "CNAME"
  content = "main.purrf.pages.dev"
  proxied = true
  ttl     = 1
  lifecycle {
    ignore_changes = [
      comment,
    ]
  }
}

resource "cloudflare_zero_trust_tunnel_cloudflared_config" "gcp_tunnel_config" {
  account_id = local.cloudflare_account_id
  tunnel_id  = local.cloudflare_tunnel_id

  config = {
    ingress = concat(
      flatten([
        for env_key, env_cfg in local.environments : [
          for func_name in local.google_cloud_function_names : {
            hostname = env_cfg.cf_host
            path     = "/purrf-${env_cfg.name}-${func_name}"
            service  = "https://us-west1-purrf-452300.cloudfunctions.net"
            origin_request = {
              http_host_header = "us-west1-purrf-452300.cloudfunctions.net"
            }
          }
        ]
      ]),
      [{
        service = "http_status:404"
      }]
    )
  }
}

resource "cloudflare_zero_trust_access_application" "purrf_app" {
  account_id = local.cloudflare_account_id
  name       = "purrf"
  domain     = local.environments.prod.origin_web
  type       = "self_hosted"
  destinations = [
    { type = "public", uri = local.environments.prod.origin_web },
    { type = "public", uri = local.environments.prod.api_host },
    { type = "public", uri = local.environments.test.origin_web },
    { type = "public", uri = local.environments.test.api_host },
    {
      type = "public"
      uri  = "*.purrf.pages.dev"
    },
  ]
  allowed_idps         = ["762bbddc-6753-4c4b-898e-89e18ecc410c", "e0e42a6d-d9a1-4e9e-9338-9643176c5fc4"]
  session_duration     = "24h"
  app_launcher_visible = true

  auto_redirect_to_identity = false
  cors_headers = {
    allow_all_methods = true
    allow_credentials = true
    allowed_headers   = ["content-type"]
    allowed_origins   = ["https://${local.environments.prod.origin_web}", "https://${local.environments.test.origin_web}"]
  }
  enable_binding_cookie      = false
  http_only_cookie_attribute = false
  options_preflight_bypass   = false
  policies = [
    {
      id         = "db15487b-4f79-4f3a-a267-1a7be4fe19f8"
      precedence = 1

    },
    { # Auth0
      id         = "791a5e24-4a75-4d7e-9f7d-5fafd25a1602"
      precedence = 2
    },
  ]

}
