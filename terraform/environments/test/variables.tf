variable "upstash_email" {
  type        = string
  description = "Upstash account email"
}

variable "upstash_api_key" {
  type        = string
  description = "Upstash Management API Key"
  sensitive   = true
}