provider "upstash" {}

provider "auth0" {}

provider "neon" {}

provider "google" {
  project = "purrf-452300"
  region  = "us-west1"
}

data "google_client_config" "provider" {
}

data "google_container_cluster" "cluster" {
  name     = "dev"
  location = "us-west1"
  project  = "circlecat"
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

provider "azurerm" {
  features {}
}
