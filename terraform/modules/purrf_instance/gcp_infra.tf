# Get purrf project details
data "google_project" "main_gcp_project_data" {
  project_id = var.gcp_project_id
}

data "google_compute_default_service_account" "default" {
}

# Create all main topics
resource "google_pubsub_topic" "topics" {
  for_each = local.pubsub_map
  name     = each.value.full_name
  labels   = local.common_labels
}

# Create all dead-letter topics
resource "google_pubsub_topic" "dlq" {
  for_each = local.pubsub_map
  name     = "${each.value.full_name}-dlq"
  labels   = local.common_labels
}

# Create main subscriptions (with dead-letter policy and expiration policy)
resource "google_pubsub_subscription" "subscriptions" {
  for_each             = local.pubsub_map
  name                 = "${each.value.full_name}-sub"
  topic                = google_pubsub_topic.topics[each.key].id
  ack_deadline_seconds = each.value.ack_deadline_seconds
  expiration_policy {
    ttl = ""
  }
  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.dlq[each.key].id
    max_delivery_attempts = each.value.max_delivery_attempts
  }
}

# Subscribe to all DLQ topics for easier failure message inspection
resource "google_pubsub_subscription" "dlq_subscriptions" {
  for_each             = local.pubsub_map
  name                 = "${each.value.full_name}-dlq-sub"
  topic                = google_pubsub_topic.dlq[each.key].id
  ack_deadline_seconds = 20
  expiration_policy {
    ttl = ""
  }
}

# Allow the Pub/Sub system service account to publish messages to the dead-letter topic
resource "google_project_iam_member" "pubsub_auto_pub_to_dlq" {
  project = var.gcp_project_id
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:service-${data.google_project.main_gcp_project_data.number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}

# Allow the Pub/Sub system service account to pull messages from subscriptions
resource "google_project_iam_member" "pubsub_auto_sub" {
  project = var.gcp_project_id
  role    = "roles/pubsub.subscriber"
  member  = "serviceAccount:service-${data.google_project.main_gcp_project_data.number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}

# Enable the Cloud Functions API
resource "google_project_service" "cloud_functions" {
  service = "cloudfunctions.googleapis.com"
}

# Enable Access Context Manager API
resource "google_project_service" "access_context_manager" {
  service = "accesscontextmanager.googleapis.com"
}

# Create a storage bucket to hold the packaged function code
resource "google_storage_bucket" "function_bucket" {
  name     = "${local.name_prefix}-function-bucket"
  location = var.gcp_region
}

# Grants public read access to the Cloud Functions code bucket
resource "google_storage_bucket_iam_binding" "purrf_internal" {
  bucket = google_storage_bucket.function_bucket.name
  role   = "roles/storage.objectViewer"
  members = [
    "allUsers",
  ]
}

# Create a dedicated service account for running Cloud Functions
resource "google_service_account" "function_sa" {
  account_id   = "${local.name_prefix}-function-sa"
  display_name = "Cloud Function Service Account"
}

# Allow the Cloud Function service account to publish messages to Pub/Sub
resource "google_project_iam_member" "function_pubsub" {
  project = var.gcp_project_id
  role    = "roles/pubsub.publisher"
  member  = google_service_account.function_sa.member
}

# Allow the Cloud Function service account to subscribe to Pub/Sub messages
resource "google_project_iam_member" "function_subscriber" {
  project = var.gcp_project_id
  role    = "roles/pubsub.subscriber"
  member  = google_service_account.function_sa.member
}

# Grant Cloud Build’s default service account the ability to manage objects in Cloud Storage
resource "google_project_iam_member" "cloud_build_storage_viewer" {
  project = var.gcp_project_id
  role    = "roles/storage.objectAdmin"
  member  = data.google_compute_default_service_account.default.member
}

# Grant Cloud Build’s default service account permission to push images to Artifact Registry
resource "google_project_iam_member" "cloud_build_artifactregistry_creator" {
  project = var.gcp_project_id
  role    = "roles/artifactregistry.createOnPushWriter"
  member  = data.google_compute_default_service_account.default.member
}


# Package and upload code for each function
data "archive_file" "function_zips" {
  for_each    = local.functions_config
  type        = "zip"
  source_dir  = each.value.source_dir
  output_path = "${path.module}/zip/function_${each.key}.zip"
}

resource "google_storage_bucket_object" "function_zips" {
  for_each = local.functions_config
  name     = "function-${each.key}-${data.archive_file.function_zips[each.key].output_base64sha256}.zip"
  bucket   = google_storage_bucket.function_bucket.name
  source   = data.archive_file.function_zips[each.key].output_path
}

# Create the Cloud Functions
resource "google_cloudfunctions_function" "functions" {
  for_each              = local.functions_config
  name                  = "${local.name_prefix}-${each.key}"
  runtime               = "python311"
  entry_point           = each.value.entry_point
  trigger_http          = true
  available_memory_mb   = each.value.memory_mb
  source_archive_bucket = google_storage_bucket.function_bucket.name
  source_archive_object = google_storage_bucket_object.function_zips[each.key].name
  service_account_email = google_service_account.function_sa.email
  ingress_settings      = "ALLOW_INTERNAL_ONLY"

  environment_variables = merge(
    each.value.env_vars,
    each.value.need_redis ? {
      REDIS_HOST     = upstash_redis_database.redis.endpoint
      REDIS_PORT     = upstash_redis_database.redis.port
      REDIS_PASSWORD = upstash_redis_database.redis.password
    } : {}
  )
}

# Grant public invocation permission (allUsers) to each Cloud Function
resource "google_cloudfunctions_function_iam_member" "invoker" {
  for_each       = local.functions_config
  cloud_function = google_cloudfunctions_function.functions[each.key].name
  role           = "roles/cloudfunctions.invoker"
  member         = "allUsers"
}
