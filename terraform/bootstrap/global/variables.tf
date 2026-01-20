variable "cloudflare_api_token" {
  type      = string
  sensitive = true
}

locals {
  environments = {
    prod = {
      name       = "prod"
      api_host   = "api.purrf.io"
      origin_web = "purrf.io"
    }
    test = {
      name       = "test"
      api_host   = "test-api.purrf.io"
      origin_web = "test.purrf.io"
    }
  }
}

variable "main_gcp_project_id" {
  type    = string
  default = "purrf-452300"
}

variable "organization_id" {
  type    = string
  default = "352575165160"
}

variable "circlecat_project_id" {
  type    = string
  default = "circlecat"
}

variable "main_gcp_region" {
  description = "GCP region"
  type        = string
  default     = "us-west1"
}