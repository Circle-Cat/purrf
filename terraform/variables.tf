variable "google_project" {
  type        = string
  description = "GCP project ID"
}

variable "google_region" {
  type        = string
  description = "Default region"
}

variable "google_zone" {
  type        = string
  description = "Default zone"
}

variable "pubsub_configs" {
  description = "List of Pub/Sub topics and subscriptions"
  type = list(object({
    name                   = string
    ack_deadline_seconds  = number
    max_delivery_attempts = number
  }))
}
