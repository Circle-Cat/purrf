# SCORM course packages. Files are served back through the backend, never
# straight from GCS, so the bucket needs no CORS configuration and no public
# access.
resource "google_storage_bucket" "training" {
  name                        = "${local.name_prefix}-training"
  location                    = var.gcp_region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"

  # Course packages are re-uploadable artefacts, not records, but a prod
  # bucket still should not vanish with a stray `terraform destroy`.
  force_destroy = !local.is_prod

  labels = local.common_labels
}

# Backend pods run as purrf-service in every environment, so bucket access is
# granted per-bucket rather than per-environment.
resource "google_storage_bucket_iam_member" "training_backend_access" {
  bucket = google_storage_bucket.training.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:purrf-service@purrf-452300.iam.gserviceaccount.com"
}

# HMAC key for the path tokens in course URLs. The content origin has no cookie
# and no Access policy, so this signature is the only thing standing between a
# URL and somebody else's course files. Held in Terraform state so it stays
# stable across applies; tainting it invalidates every token in flight, which
# costs learners a page refresh.
resource "random_password" "training_token_signing_key" {
  length  = 64
  special = false
}
