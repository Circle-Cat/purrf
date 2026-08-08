# Notification delivery.
#
# One published message is one email, not one event: the fan-out to N
# recipients happens when the rows are written, so this topic carries N
# messages and each is delivered on its own. Delivery is push rather than
# pull -- Pub/Sub calls hook.<domain>, a Cloudflare Worker verifies Google's
# OIDC token and forwards to the backend's delivery route carrying the CF
# Access service token that Pub/Sub itself cannot send.

resource "google_pubsub_topic" "notifications" {
  name   = "${local.name_prefix}-notifications"
  labels = local.common_labels
}

resource "google_pubsub_topic" "notifications_dlq" {
  name   = "${local.name_prefix}-notifications-dlq"
  labels = local.common_labels
}

# Signs the OIDC token on every push request. The Worker checks that token's
# `sub` against its ALLOWED_SUBS, so what crosses to the Worker's configuration
# is this account's numeric unique_id rather than its email -- an email can be
# recycled onto a new account, a unique_id cannot.
resource "google_service_account" "notification_pusher" {
  account_id   = "${local.name_prefix}-notify-push"
  display_name = "Signs the OIDC token on notification push requests"
}

# Pub/Sub mints that token *as* the pusher account, so Pub/Sub's own service
# agent has to be allowed to impersonate it. Without this the subscription
# still creates cleanly and every single push then fails to sign.
resource "google_service_account_iam_member" "notification_pusher_token_creator" {
  service_account_id = google_service_account.notification_pusher.name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "serviceAccount:service-${data.google_project.main_gcp_project_data.number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}

resource "google_pubsub_subscription" "notifications_push" {
  name  = "${local.name_prefix}-notifications-push-sub"
  topic = google_pubsub_topic.notifications.id

  # Must stay well below DeliveryService.CLAIM_TIMEOUT (10 minutes). A claim is
  # only stolen once it looks abandoned, so a redelivery must never overtake a
  # send that is still in flight.
  ack_deadline_seconds = 60

  # Matches the 24h shelf life. Anything Pub/Sub still holds past that would
  # only be settled `expired` by the backend, so let Pub/Sub drop it first; the
  # backend's expiry check is the belt to this braces.
  message_retention_duration = "86400s"

  expiration_policy {
    ttl = ""
  }

  push_config {
    push_endpoint = "https://${local.domains.hook}/notify"

    oidc_token {
      service_account_email = google_service_account.notification_pusher.email
      audience              = "purrf"
    }
  }

  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.notifications_dlq.id
    max_delivery_attempts = 10
  }

  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }
}

# Gives a human somewhere to look at what gave up, matching how the other
# dead-letter topics in this module are made inspectable.
resource "google_pubsub_subscription" "notifications_dlq" {
  name                 = "${local.name_prefix}-notifications-dlq-sub"
  topic                = google_pubsub_topic.notifications_dlq.id
  ack_deadline_seconds = 20

  expiration_policy {
    ttl = ""
  }
}
