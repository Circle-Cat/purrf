terraform {
  required_providers {
    upstash = {
      source = "upstash/upstash"
    }
    auth0 = {
      source = "auth0/auth0"
    }
    neon = {
      source = "kislerdm/neon"
    }
    google = {
      source = "hashicorp/google"
    }
    kubernetes = {
      source = "hashicorp/kubernetes"
    }
    azuread = {
      source = "hashicorp/azuread"
    }
    random = {
      source = "hashicorp/random"
    }
  }
}
