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
