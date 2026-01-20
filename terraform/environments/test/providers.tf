provider "upstash" {
  email   = var.upstash_email
  api_key = var.upstash_api_key
}

provider "auth0" {
  domain        = var.auth0_domain
  client_id     = var.auth0_client_id
  client_secret = var.auth0_client_secret
}

provider "neon" {
  api_key = var.neon_api_key
}