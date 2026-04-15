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
}

locals {
  # Neon database
  neon_project_name        = "${local.name_prefix}-neon"
  neon_db_name             = "${local.name_prefix}-db"
  neon_owner_role_name     = "${local.name_prefix}-owner"
  raw_host                 = data.neon_branch_endpoints.all.endpoints[0].host
  pooler_host              = replace(local.raw_host, "/^(ep-[^.]+)/", "$1-pooler")
  app_sqlalchemy_async_url = "postgresql+asyncpg://${neon_role.this.name}:${neon_role.this.password}@${local.pooler_host}/${neon_database.this.name}?ssl=require"
}

locals {
  # Pub/Sub
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
}

locals {
  # Cloud Functions
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
      env_vars = {
        AZURE_CLIENT_ID     = var.azure_client_id
        AZURE_TENANT_ID     = var.azure_tenant_id
      }
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

locals {
  # Launchdarkly
  ld_environment    = launchdarkly_project.purrf.environments[0]
  ld_sdk_key        = local.ld_environment.api_key
  ld_client_side_id = local.ld_environment.client_side_id
}
