locals {
  gmail_push_enabled   = var.gmail_watch_topic_name != ""
  gmail_watch_topic_id = "projects/${var.gcp_project_id}/topics/${var.gmail_watch_topic_name}"
}

# One topic per mailbox. Environments sharing a mailbox share this topic,
# because a mailbox holds a single watch; each environment then subscribes.
resource "google_pubsub_topic" "gmail_watch" {
  count = var.gmail_watch_topic_owner ? 1 : 0
  name  = var.gmail_watch_topic_name
}

# Gmail publishes as this Google-owned account; without it users.watch fails.
resource "google_pubsub_topic_iam_member" "gmail_watch_publisher" {
  count  = var.gmail_watch_topic_owner ? 1 : 0
  topic  = google_pubsub_topic.gmail_watch[0].id
  role   = "roles/pubsub.publisher"
  member = "serviceAccount:gmail-api-push@system.gserviceaccount.com"
}

# Signs as the notification pusher on purpose: the gateway Worker's
# ALLOWED_SUBS and the backend's NOTIFICATION_PUSHER_SUBS already admit it.
resource "google_pubsub_subscription" "gmail_push" {
  count                      = local.gmail_push_enabled ? 1 : 0
  name                       = "${local.name_prefix}-gmail-push"
  topic                      = local.gmail_watch_topic_id
  ack_deadline_seconds       = 60
  message_retention_duration = "86400s"

  expiration_policy {
    ttl = ""
  }

  push_config {
    push_endpoint = "https://${local.domains.hook}/email/gmail/push"
    oidc_token {
      service_account_email = google_service_account.notification_pusher.email
      audience              = "purrf"
    }
  }

  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }

  depends_on = [google_pubsub_topic.gmail_watch]
}
