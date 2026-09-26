# The mentorship matcher. It runs a few times a year, takes about an hour, and
# its dependencies cannot share a Python environment with the backend, so it is
# a Cloud Run job of its own rather than anything inside the app. The backend
# writes a run's input to Redis and starts the job by name; the trigger carries
# only which run to work on, and the job writes nothing to the database.
#
# Cloud Run has no imagePullSecrets, so it cannot pull the private
# purrf-matcher image from GitHub Container Registry the way the backend does on
# GKE. The image lives in one Artifact Registry repository in purrf-452300, the
# project every environment's job runs in, and every environment pulls from it:
# the same image is what runs everywhere, so a repository per environment would
# only mean copying it. Being in the job's own project, it needs no grant --
# the project's Cloud Run service agent can already pull from it. The
# repository is created by hand once, not here, because this module runs once
# per environment. The image is built and pushed by hand this round, which is
# why the tag is an explicit variable.

# Left on when the matcher is removed. Every environment shares purrf-452300,
# and Cloud Functions gen 2 runs on Cloud Run, so disabling either API on
# destroy would take it away from staging and prod too.
resource "google_project_service" "matcher" {
  for_each = var.enable_matcher ? toset([
    "run.googleapis.com",
    "secretmanager.googleapis.com",
  ]) : toset([])

  service            = each.value
  disable_on_destroy = false
}

resource "google_service_account" "matcher_job" {
  count = var.enable_matcher ? 1 : 0

  account_id   = "${local.name_prefix}-matcher-job"
  display_name = "Mentorship matcher job"
}

# The password of the database the backend already uses. Unlike the LLM key
# below, the value is written here rather than by hand: Terraform holds this
# password in state either way, because the same attribute is what configures
# the backend (see deploy.tf), so keeping it out of one resource would protect
# nothing.
resource "google_secret_manager_secret" "matcher_redis_password" {
  count = var.enable_matcher ? 1 : 0

  secret_id = "${local.name_prefix}-matcher-redis-password"
  labels    = local.common_labels

  replication {
    auto {}
  }

  depends_on = [google_project_service.matcher]
}

resource "google_secret_manager_secret_version" "matcher_redis_password" {
  count = var.enable_matcher ? 1 : 0

  secret      = google_secret_manager_secret.matcher_redis_password[0].id
  secret_data = upstash_redis_database.redis.password
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

# A real key is added by hand with `gcloud secrets versions add` so it never
# reaches the state file. In stub mode no LLM is called, but the job still
# resolves the secret's latest version when it is created, so a placeholder is
# written here. It is not a key and is safe in state. Turning stub mode off
# destroys this version: add the real key by hand first.
resource "google_secret_manager_secret_version" "matcher_llm_api_key_placeholder" {
  count = var.enable_matcher && var.matcher_llm_stub ? 1 : 0

  secret      = google_secret_manager_secret.matcher_llm_api_key[0].id
  secret_data = "unused-in-stub-mode"
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
        image = "${local.matcher_image_location}-docker.pkg.dev/${local.matcher_image_project}/${local.matcher_image_repository}/purrf-matcher:${var.matcher_image_tag}"

        resources {
          limits = {
            cpu    = "1"
            memory = "2Gi"
          }
        }

        # RUN_ID, and optionally RUN_DATE, arrive as container overrides on
        # the trigger; everything else about a run is read from Redis, under
        # keys named after that run id.
        env {
          name  = "REDIS_HOST"
          value = upstash_redis_database.redis.endpoint
        }

        env {
          name  = "REDIS_PORT"
          value = tostring(upstash_redis_database.redis.port)
        }

        # Through Secret Manager, not a plain env value: everything in a job's
        # env is readable by anyone who can describe the job, and this password
        # opens the same database the backend uses.
        env {
          name = "REDIS_PASSWORD"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.matcher_redis_password[0].secret_id
              version = "latest"
            }
          }
        }

        # Where the job reports that a run finished. It signs its own token for
        # this, as itself, so nothing is granted here -- but the Worker in
        # front of it only accepts subs on an allow-list, which is why
        # matcher_job_sub is an output (see outputs.tf).
        env {
          name  = "PURRF_CALLBACK_URL"
          value = "https://${local.domains.hook}/mentorship/match-runs/complete"
        }

        env {
          name  = "PURRF_CALLBACK_AUDIENCE"
          value = "purrf"
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

        # The matcher calls no LLM and writes fake scores, and its output says
        # so: matcher_version carries +llm-stub.
        dynamic "env" {
          for_each = var.matcher_llm_stub ? ["1"] : []
          content {
            name  = "MATCHER_LLM_STUB"
            value = env.value
          }
        }
      }
    }
  }

  depends_on = [
    google_project_service.matcher,
    google_secret_manager_secret_version.matcher_llm_api_key_placeholder,
  ]
}

resource "google_secret_manager_secret_iam_member" "matcher_redis_password_job_access" {
  count = var.enable_matcher ? 1 : 0

  secret_id = google_secret_manager_secret.matcher_redis_password[0].id
  role      = "roles/secretmanager.secretAccessor"
  member    = google_service_account.matcher_job[0].member
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
