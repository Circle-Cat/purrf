terraform {
  required_providers {
    upstash = {
      source  = "upstash/upstash"
      version = "1.5.3"
    }
    auth0 = {
      source  = "auth0/auth0"
      version = ">= 1.0.0"
    }
  }
}