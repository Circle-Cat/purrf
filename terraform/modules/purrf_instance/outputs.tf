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
