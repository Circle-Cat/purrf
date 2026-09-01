# SCORM course packages for the training module.
#
# An uploaded .zip is expanded into a per-upload prefix
# (`training/{course_id}/{uuid}/`) and every file is served back through the
# backend, never straight from GCS: the bucket therefore needs no CORS
# configuration and no public access. Overwriting a course writes a fresh
# prefix and flips the pointer, so the bucket accumulates one dead prefix per
# overwrite until the delayed cleanup removes it.
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

# Same shared service account as every other bucket: backend pods run as
# purrf-service across all environments (google_service_account_iam_member
# .purrf_service_wi in deploy.tf), so access is granted per-bucket.
resource "google_storage_bucket_iam_member" "training_backend_access" {
  bucket = google_storage_bucket.training.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:purrf-service@purrf-452300.iam.gserviceaccount.com"
}

# HMAC key signing the short-lived content tokens that appear in course URLs
# (`https://<training-content host>/p/<token>/...`). The content origin has no
# cookie and no Access policy in front of it, so this signature is the only
# thing standing between a URL and somebody else's course files.
#
# Generated and held in Terraform state so it stays stable across applies;
# rotate by tainting this resource. Rotation invalidates every token in flight,
# which costs learners a page refresh and nothing more -- tokens live 12 hours
# and carry no progress.
resource "random_password" "training_token_signing_key" {
  length  = 64
  special = false
}
