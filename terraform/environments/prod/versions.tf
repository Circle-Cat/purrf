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
    neon = {
      source  = "kislerdm/neon"
      version = ">= 0.2.2"
    }
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 3.1"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.0"
    }
    postgresql = {
      source  = "cyrilgdn/postgresql"
      version = "~> 1.22"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
}
