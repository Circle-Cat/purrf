terraform {
  backend "gcs" {
    bucket = "purrf-config-bucket"
    prefix = "terraform.tfstate"
  }
}
