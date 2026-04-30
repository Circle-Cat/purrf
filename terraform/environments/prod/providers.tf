provider "upstash" {}

provider "auth0" {}

provider "neon" {}

provider "google" {
  project = "purrf-452300"
  region  = "us-east4"
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

# Connect to Neon as the owner role to manage roles/grants declaratively.
# Uses the direct (non-pooler) host because pgbouncer rejects role/DDL ops.
# superuser=false is required on Neon — the provider otherwise tries RESET ROLE
# after each statement, which only superusers can do.
provider "postgresql" {
  scheme    = "postgres"
  host      = module.purrf_instance.neon_direct_host
  port      = 5432
  database  = module.purrf_instance.neon_db_name
  username  = module.purrf_instance.neon_owner_role_name
  password  = module.purrf_instance.neon_owner_password
  sslmode   = "require"
  superuser = false
}
