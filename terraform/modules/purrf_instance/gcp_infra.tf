# Get purrf project details
data "google_project" "main_gcp_project_data" {
  project_id = var.gcp_project_id
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
