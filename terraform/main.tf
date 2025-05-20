# Create all main topics
resource "google_pubsub_topic" "topics" {
  for_each = { for cfg in var.pubsub_configs : cfg.name => cfg }
  name    = each.key
}

# Create all dead-letter topics
resource "google_pubsub_topic" "dlq" {
  for_each = { for cfg in var.pubsub_configs : cfg.name => cfg }
  name    = "${each.key}_dlq"
}

# Create main subscriptions (with dead-letter policy and expiration policy)
resource "google_pubsub_subscription" "subscriptions" {
  for_each = { for cfg in var.pubsub_configs : cfg.name => cfg }
  name  = "${each.key}_sub"
  topic = google_pubsub_topic.topics[each.key].id
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
  for_each = { for cfg in var.pubsub_configs : cfg.name => cfg }
  name  = "${each.key}_dlq_sub"
  topic = google_pubsub_topic.dlq[each.key].id
  ack_deadline_seconds = 20
  expiration_policy {
    ttl = ""
  }
}
