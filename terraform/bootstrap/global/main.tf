resource "cloudflare_ruleset" "cors_headers" {
  zone_id = "9a0308ba411ef3466582881dcd274f18"
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
            value     = "GET, POST, OPTIONS, DELETE, PUT"
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
  zone_id = "9a0308ba411ef3466582881dcd274f18"
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