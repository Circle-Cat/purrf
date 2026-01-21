locals {
  environments = {
    prod = {
      name       = "prod"
      api_host   = "api.purrf.io"
      origin_web = "purrf.io"
      cf_host    = "cf.purrf.io"
    }
    test = {
      name       = "test"
      api_host   = "test-api.purrf.io"
      origin_web = "test.purrf.io"
      cf_host    = "test-cf.purrf.io"
    }
  }

  webhook_ips = [
    # Microsoft webhook IP ranges
    "20.20.32.0/19",
    "20.190.128.0/18",
    "20.231.128.0/19",
    "40.126.0.0/18",
    "20.140.232.0/23",
    "52.126.194.0/23",
    "40.72.70.0/23",
    "52.130.2.32/27",
    "52.130.3.64/27",
    "52.130.17.192/27",
    "52.130.18.32/27",
    # Gerrit webhook IP ranges
    "140.83.87.89/32"
  ]
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