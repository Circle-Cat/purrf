provider "google" {
  project = var.google_project
  region  = var.google_region
  zone    = var.google_zone

  billing_project       = var.google_project
  user_project_override = true
}