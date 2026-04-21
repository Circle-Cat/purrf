provider "upstash" {}

provider "auth0" {}

provider "neon" {}

provider "google" {
  project = "purrf-452300"
  region  = "us-east4"
}

provider "launchdarkly" {
  access_token = var.launchdarkly_access_token
}

data "google_client_config" "provider" {
}

data "google_container_cluster" "cluster" {
  name     = "prod"
  location = "us-east4"
  project  = "circlecat-prod-iad"
}

provider "helm" {
  kubernetes = {
    host  = "https://${data.google_container_cluster.cluster.endpoint}"
    token = data.google_client_config.provider.access_token
    exec = {
      api_version = "client.authentication.k8s.io/v1beta1"
      command     = "gke-gcloud-auth-plugin"
    }
  }
}

provider "kubernetes" {
  host  = "https://${data.google_container_cluster.cluster.endpoint}"
  token = data.google_client_config.provider.access_token
  exec {
    api_version = "client.authentication.k8s.io/v1beta1"
    command     = "gke-gcloud-auth-plugin"
  }
}

provider "azurerm" {
  features {}
}
