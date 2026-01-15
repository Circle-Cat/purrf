resource "upstash_redis_database" "redis" {
  database_name  = "purrf-redis-${var.env_name}"
  region         = "gcp-global"
  primary_region = "us-east4"
  tls            = true
}
