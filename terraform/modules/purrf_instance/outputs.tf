# Computed domain names for this Purrf instance.
output "computed_domains" {
  value = local.domains
}

# Resource name prefix used by this module.
output "resource_prefix" {
  value = local.name_prefix
}

output "redis_endpoint" {
  value = upstash_redis_database.redis.endpoint
}

output "redis_password" {
  value     = upstash_redis_database.redis.password
  sensitive = true
}

output "redis_port" {
  value = upstash_redis_database.redis.port
}

output "auth0_client_id" {
  value = auth0_client.purrf_auth0.client_id
}

output "auth0_client_secret" {
  value     = auth0_client_credentials.purrf_auth0.client_secret
  sensitive = true
}

output "neon_project_id" {
  value = neon_project.this.id
}

output "neon_default_branch_id" {
  value = neon_project.this.default_branch_id
}
output "neon_database_owner" {
  value = neon_project.this.database_user
}

output "neon_direct_host" {
  value = local.raw_host
}

output "neon_pooler_host" {
  value = local.pooler_host
}

output "neon_db_name" {
  value = neon_database.this.name
}

output "neon_owner_role_name" {
  value = neon_role.this.name
}

output "neon_owner_password" {
  value     = neon_role.this.password
  sensitive = true
}

output "default_account" {
  value = data.google_compute_default_service_account.default.email
}

output "gcp_project_id" {
  value = var.gcp_project_id
}

output "chat_google_events_topic_id" {
  value = google_pubsub_topic.topics["chat-google-events"].name
}

output "resume_bucket_name" {
  value = google_storage_bucket.resumes.name
}

output "microsoft_chat_notification_url" {
  value = "https://${local.domains.cf}/${local.name_prefix}-microsoft-chat"
}

output "microsoft_chat_lifecycle_notification_url" {
  value = "https://${local.domains.cf}/${local.name_prefix}-microsoft-chat-lifecycle"
}

output "auth0_custom_domain_cname" {
  value = auth0_custom_domain.purrf_custom_domain.verification[0].methods[0].record
}

# Default Auth0 tenant domain (e.g. purrf-test-cd-xxx.us.auth0.com). Use this
# value as the MGMT_DOMAIN secret on the post-login Action, NOT the
# Cloudflare-fronted custom domain.
output "auth0_management_domain" {
  value = data.auth0_tenant.current.domain
}

output "auth0_link_action_m2m_client_id" {
  value = auth0_client.link_action_m2m.client_id
}

output "auth0_link_action_m2m_client_secret" {
  value     = auth0_client_credentials.link_action_m2m.client_secret
  sensitive = true
}
