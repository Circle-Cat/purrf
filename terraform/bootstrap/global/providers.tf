provider "cloudflare" {}

provider "google" {
  project               = var.main_gcp_project_id
  region                = var.main_gcp_region
  billing_project       = var.main_gcp_project_id
  user_project_override = true
}