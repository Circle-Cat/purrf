terraform {
  backend "gcs" {
    bucket = "purrf-terraform-state"
    prefix = "test"
  }
}
