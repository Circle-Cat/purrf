variable "env_name" {
  description = "Environment name: prod, test, or staging"
  type        = string
  validation {
    condition     = contains(["prod", "test", "staging"], var.env_name)
    error_message = "env_name must be one of: prod, test, staging."
  }
}

variable "base_domain" {
  description = "Base domain name"
  type        = string
  default     = "purrf.io"
}

variable "gcp_project_id" {
  description = "GCP project ID"
  type        = string
}

variable "gcp_region" {
  description = "GCP region"
  type        = string
  default     = "us-west1"
}

variable "neon_org_id" {
  type = string
}

variable "cloudflare_account_id" {
  description = "Cloudflare Account ID"
  type        = string
}

variable "cloudflare_zone_id" {
  description = "Cloudflare Zone ID"
  type        = string
}

variable "cloudflare_tunnel_id" {
  description = "Cloudflare Tunnel ID"
  type        = string
}

variable "microsoft_chat_code_dir" {
  type        = string
  description = "The relative path to the Microsoft Chat producer source code directory."
}

variable "microsoft_chat_entry_point" {
  type        = string
  description = "The name of the Python function to be executed for Microsoft Chat."
}

variable "microsoft_lifecycle_code_dir" {
  type        = string
  description = "The relative path to the Microsoft Lifecycle handler source code directory."
}

variable "microsoft_lifecycle_entry_point" {
  type        = string
  description = "The name of the Python function to be executed for Microsoft Lifecycle events."
}

variable "gerrit_producer_code_dir" {
  type        = string
  description = "The relative path to the Gerrit producer source code directory."
}

variable "gerrit_producer_entry_point" {
  type        = string
  description = "The name of the Python function to be executed for Gerrit events."
}

variable "auth0_callbacks" {
  type        = list(string)
  description = "Allowed callback URLs for Auth0"
}

variable "auth0_logout_urls" {
  type        = list(string)
  description = "Allowed logout URLs for Auth0"
}

variable "image_tag" {
  type        = string
  description = "Deployed image tag"
}

variable "jira_password" {
  type      = string
  sensitive = true
}

variable "gerrit_http_pass" {
  type      = string
  sensitive = true
}

locals {
  # Derived values based on environment configuration
  is_prod = var.env_name == "prod"

  name_prefix = "purrf-${var.env_name}"

  subdomain_prefix  = local.is_prod ? "" : "${var.env_name}-"
  env_domain_prefix = local.is_prod ? "" : "${var.env_name}."

  domains = {
    main  = "${local.env_domain_prefix}${var.base_domain}"
    api   = "${local.subdomain_prefix}api.${var.base_domain}"
    login = "${local.subdomain_prefix}login.${var.base_domain}"
    cf    = "${local.subdomain_prefix}cf.${var.base_domain}"
  }

  common_labels = {
    env        = var.env_name
    managed_by = "terraform"
    project    = "purrf"
  }

  neon_project_name        = "${local.name_prefix}-neon"
  neon_db_name             = "${local.name_prefix}-db"
  neon_owner_role_name     = "${local.name_prefix}-owner"
  app_sqlalchemy_async_url = "postgresql+asyncpg://${neon_role.this.name}:${neon_role.this.password}@${neon_project.this.default_branch_id}.aws-us-east-1.aws.neon.tech/${neon_database.this.name}?ssl=require"

  pubsub_names = [
    "chat-google-events",
    "chat-microsoft-events",
    "gerrit-events"
  ]

  pubsub_map = {
    for name in local.pubsub_names : name => {
      full_name             = "${local.name_prefix}-${name}"
      ack_deadline_seconds  = 20
      max_delivery_attempts = 5
    }
  }

  functions_config = {
    "microsoft-chat" = {
      source_dir  = "${path.module}/${var.microsoft_chat_code_dir}"
      entry_point = var.microsoft_chat_entry_point
      memory_mb   = 256
      need_redis  = true
      env_vars = {
        PROJECT_ID = var.gcp_project_id
        TOPIC_ID   = google_pubsub_topic.topics["chat-microsoft-events"].name
      }
    },
    "microsoft-chat-lifecycle" = {
      source_dir  = "${path.module}/${var.microsoft_lifecycle_code_dir}"
      entry_point = var.microsoft_lifecycle_entry_point
      memory_mb   = 256
      need_redis  = true
      env_vars    = {}
    },
    "gerrit-events" = {
      source_dir  = "${path.module}/${var.gerrit_producer_code_dir}"
      entry_point = var.gerrit_producer_entry_point
      memory_mb   = 256
      need_redis  = true
      env_vars = {
        PROJECT_ID = var.gcp_project_id
        TOPIC_ID   = google_pubsub_topic.topics["gerrit-events"].name
      }
    }
  }
}
