# Content-addressed résumé storage for the recruiting module.
# See backend/recruiting/resume_storage.py.
resource "google_storage_bucket" "resumes" {
  name                        = "${local.name_prefix}-resumes"
  location                    = var.gcp_region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"

  # Résumés are PII; only allow accidental `terraform destroy` to remove a
  # non-empty bucket in non-prod environments.
  force_destroy = !local.is_prod

  labels = local.common_labels
}

# Backend pods run as this one shared service account across every
# environment (see google_service_account_iam_member.purrf_service_wi in
# deploy.tf), so access is scoped per-bucket rather than per-project.
resource "google_storage_bucket_iam_member" "resumes_backend_access" {
  bucket = google_storage_bucket.resumes.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:purrf-service@purrf-452300.iam.gserviceaccount.com"
}
