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

output "auth0_client_id" {
  value = auth0_client.purrf_auth0.client_id
}

output "neon_project_id" {
  value = neon_project.this.id
}

output "neon_default_branch_id" {
  value = neon_project.this.default_branch_id
}
output "neon_database_user" {
  value = neon_project.this.database_user
}