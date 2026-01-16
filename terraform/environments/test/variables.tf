variable "upstash_email" {
  type        = string
  description = "Upstash account email"
}

variable "upstash_api_key" {
  type        = string
  description = "Upstash Management API Key"
  sensitive   = true
}

variable "auth0_domain" {
  type = string
}

variable "auth0_client_id" {
  type = string
}

variable "auth0_client_secret" {
  type      = string
  sensitive = true
}