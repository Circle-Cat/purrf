google_project = "purrf-452300"
google_region  = "us-west1"
google_zone    = "us-west1-a"

pubsub_configs = [
  {
    name                   = "chat_google_events"
    ack_deadline_seconds  = 20
    max_delivery_attempts = 5
  },
  {
    name                   = "chat_microsoft_events"
    ack_deadline_seconds  = 20
    max_delivery_attempts = 5
  }
]
