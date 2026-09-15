# The mentorship matcher. It runs a few times a year, takes about an hour, and
# its dependencies cannot share a Python environment with the backend, so it is
# a Cloud Run job of its own rather than anything inside the app. The backend
# writes a payload to the bucket below and starts the job by name; nothing about
# a run travels through the trigger and the job writes nothing to the database.
#
# Cloud Run has no imagePullSecrets, so it cannot pull the private
# purrf-matcher image from GitHub Container Registry the way the backend does on
# GKE. The image has to live in Artifact Registry; this round it is built and
# pushed by hand, which is why the tag is an explicit variable.

resource "google_project_service" "matcher" {
  for_each = var.enable_matcher ? toset([
    "artifactregistry.googleapis.com",
    "run.googleapis.com",
    "secretmanager.googleapis.com",
  ]) : toset([])

  service = each.value
}

resource "google_artifact_registry_repository" "matcher" {
  count = var.enable_matcher ? 1 : 0

  repository_id = "${local.name_prefix}-matcher"
  location      = var.gcp_region
  format        = "DOCKER"
  description   = "Images for the mentorship matcher job."
  labels        = local.common_labels

  depends_on = [google_project_service.matcher]
}

# Input payloads and, once a run finishes, everything the job writes back under
# the same run prefix. Both sides need to reach it, so it is granted twice
# below.
resource "google_storage_bucket" "matching" {
  count = var.enable_matcher ? 1 : 0

  name                        = "${local.name_prefix}-matching"
  location                    = var.gcp_region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"

  # A run's inputs and results are what makes its pairs explainable after the
  # fact, so prod keeps them even through a stray `terraform destroy`.
  force_destroy = !local.is_prod

  labels = local.common_labels
}

resource "google_service_account" "matcher_job" {
  count = var.enable_matcher ? 1 : 0

  account_id   = "${local.name_prefix}-matcher-job"
  display_name = "Mentorship matcher job"
}

# Only the container is Terraform-managed. The key itself is added by hand with
# `gcloud secrets versions add` so it never reaches the state file.
resource "google_secret_manager_secret" "matcher_llm_api_key" {
  count = var.enable_matcher ? 1 : 0

  secret_id = "${local.name_prefix}-matcher-llm-api-key"
  labels    = local.common_labels

  replication {
    auto {}
  }

  depends_on = [google_project_service.matcher]
}

resource "google_cloud_run_v2_job" "matcher" {
  count = local.matcher_job_enabled ? 1 : 0

  name     = "${local.name_prefix}-matcher"
  location = var.gcp_region
  labels   = local.common_labels

  template {
    task_count = 1

    template {
      service_account = google_service_account.matcher_job[0].email

      # A run scores every mentor against every mentee through an LLM, so six
      # hours is headroom over the hour it takes, not an expectation. Retrying
      # is worse than not: a retry would pay for the whole scoring pass again
      # and overwrite the results of the attempt that failed halfway.
      max_retries = 0
      timeout     = "21600s"

      containers {
        image = "${var.gcp_region}-docker.pkg.dev/${var.gcp_project_id}/${google_artifact_registry_repository.matcher[0].repository_id}/purrf-matcher:${var.matcher_image_tag}"

        resources {
          limits = {
            cpu    = "1"
            memory = "2Gi"
          }
        }

        # RUN_ID, and optionally RUN_DATE, arrive as container overrides on the
        # trigger; everything else about a run is read from the bucket.
        env {
          name  = "MATCHING_BUCKET"
          value = google_storage_bucket.matching[0].name
        }

        env {
          name  = "LLM_CONCURRENCY"
          value = tostring(var.matcher_llm_concurrency)
        }

        env {
          name = "DEEPSEEK_API_KEY"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.matcher_llm_api_key[0].secret_id
              version = "latest"
            }
          }
        }
      }
    }
  }

  depends_on = [google_project_service.matcher]
}

resource "google_storage_bucket_iam_member" "matching_job_access" {
  count = var.enable_matcher ? 1 : 0

  bucket = google_storage_bucket.matching[0].name
  role   = "roles/storage.objectAdmin"
  member = google_service_account.matcher_job[0].member
}

# Backend pods run as purrf-service in every environment, so bucket access is
# granted per-bucket rather than per-environment.
resource "google_storage_bucket_iam_member" "matching_backend_access" {
  count = var.enable_matcher ? 1 : 0

  bucket = google_storage_bucket.matching[0].name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:purrf-service@purrf-452300.iam.gserviceaccount.com"
}

resource "google_secret_manager_secret_iam_member" "matcher_llm_api_key_job_access" {
  count = var.enable_matcher ? 1 : 0

  secret_id = google_secret_manager_secret.matcher_llm_api_key[0].id
  role      = "roles/secretmanager.secretAccessor"
  member    = google_service_account.matcher_job[0].member
}

# The backend triggers the job with container overrides, which needs
# run.jobs.runWithOverrides -- a permission roles/run.invoker does not carry.
# The predefined roles/run.jobsExecutorWithOverrides is exactly that permission
# plus run.jobs.run, so neither roles/run.developer (which can also change and
# delete the job) nor a custom role is needed. Bound on the one job, not the
# project.
resource "google_cloud_run_v2_job_iam_member" "matcher_backend_executor" {
  count = local.matcher_job_enabled ? 1 : 0

  name     = google_cloud_run_v2_job.matcher[0].name
  location = google_cloud_run_v2_job.matcher[0].location
  role     = "roles/run.jobsExecutorWithOverrides"
  member   = "serviceAccount:purrf-service@purrf-452300.iam.gserviceaccount.com"
}
