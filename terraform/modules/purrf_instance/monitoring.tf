# Cloud Monitoring alerts. Everything here is created only when var.alerting
# is set.
#
# Policies live where their data lives: Pub/Sub, Cloud Functions and the
# matcher job are in the GCP project; the backend's pods and logs
# are in the cluster's project (k8s_project_id), so its metrics, log-based
# metrics and the policies on them are made there. Each project gets its own
# copy of the notification channels, since a policy can only notify channels in
# its own project.
#
# Gerrit is left out on purpose: its server is being shut down. Reachability
# of the backend from outside is watched by Uptime Kuma, not here.

locals {
  alerting_enabled = var.alerting != null
  # The Chat channel waits until a space has the Monitoring app installed.
  alert_chat_enabled = try(var.alerting.chat_space, "") != ""

  # Subscriptions that deliver to the backend. Gerrit's is excluded.
  alert_delivery_subscriptions = concat(
    [
      google_pubsub_subscription.subscriptions["chat-google-events"].name,
      google_pubsub_subscription.subscriptions["chat-microsoft-events"].name,
      google_pubsub_subscription.notifications_push.name,
    ],
    local.gmail_push_enabled ? [google_pubsub_subscription.gmail_push[0].name] : [],
  )

  # Subscriptions on the dead-letter topics: anything here gave up delivering.
  alert_dead_letter_subscriptions = [
    google_pubsub_subscription.dlq_subscriptions["chat-google-events"].name,
    google_pubsub_subscription.dlq_subscriptions["chat-microsoft-events"].name,
    google_pubsub_subscription.notifications_dlq.name,
  ]

  alert_functions = [
    google_cloudfunctions_function.functions["microsoft-chat"].name,
    google_cloudfunctions_function.functions["microsoft-chat-lifecycle"].name,
  ]

  # Monitoring filters take a quoted, comma-separated list inside one_of().
  alert_delivery_subscriptions_one_of    = join(",", [for s in local.alert_delivery_subscriptions : "\"${s}\""])
  alert_dead_letter_subscriptions_one_of = join(",", [for s in local.alert_dead_letter_subscriptions : "\"${s}\""])
  alert_functions_one_of                 = join(",", [for f in local.alert_functions : "\"${f}\""])

  # The backend pod: the chart names its container after the chart.
  alert_backend_container_filter = join(" AND ", [
    "resource.type=\"k8s_container\"",
    "resource.labels.namespace_name=\"${local.name_prefix}\"",
    "resource.labels.container_name=\"prod\"",
  ])

  alert_gcp_channels = concat(
    google_monitoring_notification_channel.email_gcp[*].id,
    google_monitoring_notification_channel.chat_gcp[*].id,
  )
  alert_k8s_channels = concat(
    google_monitoring_notification_channel.email_k8s[*].id,
    google_monitoring_notification_channel.chat_k8s[*].id,
  )
}

# ---------------------------------------------------------------------------
# Notification channels, one set per project
# ---------------------------------------------------------------------------

resource "google_monitoring_notification_channel" "email_gcp" {
  count        = local.alerting_enabled ? 1 : 0
  project      = var.gcp_project_id
  display_name = "${local.name_prefix} alerts email"
  type         = "email"
  labels = {
    email_address = var.alerting.email
  }
}

resource "google_monitoring_notification_channel" "chat_gcp" {
  count        = local.alert_chat_enabled ? 1 : 0
  project      = var.gcp_project_id
  display_name = "${local.name_prefix} alerts chat"
  type         = "google_chat"
  labels = {
    space = "spaces/${var.alerting.chat_space}"
  }
}

resource "google_monitoring_notification_channel" "email_k8s" {
  count        = local.alerting_enabled ? 1 : 0
  project      = var.k8s_project_id
  display_name = "${local.name_prefix} alerts email"
  type         = "email"
  labels = {
    email_address = var.alerting.email
  }
}

resource "google_monitoring_notification_channel" "chat_k8s" {
  count        = local.alert_chat_enabled ? 1 : 0
  project      = var.k8s_project_id
  display_name = "${local.name_prefix} alerts chat"
  type         = "google_chat"
  labels = {
    space = "spaces/${var.alerting.chat_space}"
  }
}

# ---------------------------------------------------------------------------
# Pub/Sub
# ---------------------------------------------------------------------------

resource "google_monitoring_alert_policy" "pubsub_dead_letter" {
  count                 = local.alerting_enabled ? 1 : 0
  project               = var.gcp_project_id
  display_name          = "${local.name_prefix}: messages in a dead-letter subscription"
  combiner              = "OR"
  notification_channels = local.alert_gcp_channels

  conditions {
    display_name = "Undelivered messages in a dead-letter subscription"
    condition_threshold {
      filter          = "resource.type=\"pubsub_subscription\" AND metric.type=\"pubsub.googleapis.com/subscription/num_undelivered_messages\" AND resource.labels.subscription_id=one_of(${local.alert_dead_letter_subscriptions_one_of})"
      comparison      = "COMPARISON_GT"
      threshold_value = 0
      duration        = "0s"
      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_MAX"
      }
    }
  }

  documentation {
    mime_type = "text/markdown"
    content   = "A message was given up on after every delivery attempt and moved to a dead-letter topic. Look at it in the named subscription, fix the cause, then acknowledge or purge it. The alert stays open while the message is there."
  }
}

resource "google_monitoring_alert_policy" "pubsub_backlog" {
  count                 = local.alerting_enabled ? 1 : 0
  project               = var.gcp_project_id
  display_name          = "${local.name_prefix}: Pub/Sub delivery is falling behind"
  combiner              = "OR"
  notification_channels = local.alert_gcp_channels

  conditions {
    display_name = "Oldest unacknowledged message older than 30 minutes"
    condition_threshold {
      filter          = "resource.type=\"pubsub_subscription\" AND metric.type=\"pubsub.googleapis.com/subscription/oldest_unacked_message_age\" AND resource.labels.subscription_id=one_of(${local.alert_delivery_subscriptions_one_of})"
      comparison      = "COMPARISON_GT"
      threshold_value = 1800
      duration        = "600s"
      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_MAX"
      }
    }
  }

  documentation {
    mime_type = "text/markdown"
    content   = "Pub/Sub has held a message for more than 30 minutes without the backend acknowledging it. Usually the backend or the hook Worker is down or answering with errors; check the push failure alert and the backend logs."
  }
}

resource "google_monitoring_alert_policy" "pubsub_push_failures" {
  count                 = local.alerting_enabled ? 1 : 0
  project               = var.gcp_project_id
  display_name          = "${local.name_prefix}: Pub/Sub push requests failing"
  combiner              = "OR"
  notification_channels = local.alert_gcp_channels

  conditions {
    display_name = "More than 20 failed push requests in 10 minutes"
    condition_threshold {
      filter          = "resource.type=\"pubsub_subscription\" AND metric.type=\"pubsub.googleapis.com/subscription/push_request_count\" AND metric.labels.response_class!=\"ack\" AND resource.labels.subscription_id=one_of(${local.alert_delivery_subscriptions_one_of})"
      comparison      = "COMPARISON_GT"
      threshold_value = 20
      duration        = "0s"
      aggregations {
        alignment_period     = "600s"
        per_series_aligner   = "ALIGN_DELTA"
        cross_series_reducer = "REDUCE_SUM"
        group_by_fields      = ["resource.labels.subscription_id"]
      }
    }
  }

  documentation {
    mime_type = "text/markdown"
    content   = "Pushes to the hook Worker are being refused or timing out. A few during a backend rollout are normal; this many means deliveries are failing. Check the backend logs and the hook Worker."
  }
}

# ---------------------------------------------------------------------------
# Cloud Functions
# ---------------------------------------------------------------------------

resource "google_monitoring_alert_policy" "function_errors" {
  count                 = local.alerting_enabled ? 1 : 0
  project               = var.gcp_project_id
  display_name          = "${local.name_prefix}: Cloud Function errors"
  combiner              = "OR"
  notification_channels = local.alert_gcp_channels

  conditions {
    display_name = "A function execution did not finish ok"
    condition_threshold {
      filter          = "resource.type=\"cloud_function\" AND metric.type=\"cloudfunctions.googleapis.com/function/execution_count\" AND metric.labels.status!=\"ok\" AND resource.labels.function_name=one_of(${local.alert_functions_one_of})"
      comparison      = "COMPARISON_GT"
      threshold_value = 0
      duration        = "0s"
      aggregations {
        alignment_period     = "300s"
        per_series_aligner   = "ALIGN_DELTA"
        cross_series_reducer = "REDUCE_SUM"
        group_by_fields      = ["resource.labels.function_name"]
      }
    }
  }

  documentation {
    mime_type = "text/markdown"
    content   = "A Teams webhook function failed. Its logs are under Cloud Run functions in this project."
  }
}

# A removed or missed Teams subscription is only logged as a warning by the
# lifecycle function and never recreated, so the chat goes quiet with no error.
resource "google_monitoring_alert_policy" "teams_lifecycle_warning" {
  count                 = local.alerting_enabled ? 1 : 0
  project               = var.gcp_project_id
  display_name          = "${local.name_prefix}: Teams subscription removed or missed"
  combiner              = "OR"
  notification_channels = local.alert_gcp_channels

  conditions {
    display_name = "Lifecycle function logged a warning"
    condition_matched_log {
      filter = "resource.type=\"cloud_function\" AND resource.labels.function_name=\"${google_cloudfunctions_function.functions["microsoft-chat-lifecycle"].name}\" AND severity>=WARNING"
    }
  }

  alert_strategy {
    notification_rate_limit {
      period = "3600s"
    }
    auto_close = "86400s"
  }

  documentation {
    mime_type = "text/markdown"
    content   = "Microsoft Graph removed a Teams chat subscription, or reported missed notifications. Purrf does not recreate it, so that chat stops arriving. Read the log line for the subscription id, then subscribe the chat again with POST /api/microsoft/chat/subscribe. Never do this from a non-prod environment against a real chat: it deletes prod's subscription."
  }
}

# ---------------------------------------------------------------------------
# Matcher job
# ---------------------------------------------------------------------------

resource "google_monitoring_alert_policy" "matcher_failed" {
  count                 = local.alerting_enabled && local.matcher_job_enabled ? 1 : 0
  project               = var.gcp_project_id
  display_name          = "${local.name_prefix}: matcher run failed"
  combiner              = "OR"
  notification_channels = local.alert_gcp_channels

  conditions {
    display_name = "A matcher execution failed"
    condition_threshold {
      filter          = "resource.type=\"cloud_run_job\" AND metric.type=\"run.googleapis.com/job/completed_execution_count\" AND metric.labels.result=\"failed\" AND resource.labels.job_name=\"${google_cloud_run_v2_job.matcher[0].name}\""
      comparison      = "COMPARISON_GT"
      threshold_value = 0
      duration        = "0s"
      aggregations {
        alignment_period     = "300s"
        per_series_aligner   = "ALIGN_DELTA"
        cross_series_reducer = "REDUCE_SUM"
      }
    }
  }

  documentation {
    mime_type = "text/markdown"
    content   = "A matching run's Cloud Run job failed. Its logs are on the job's execution page in Cloud Run."
  }
}

# ---------------------------------------------------------------------------
# Backend pod and logs (cluster project)
# ---------------------------------------------------------------------------

resource "google_monitoring_alert_policy" "backend_restarts" {
  count                 = local.alerting_enabled ? 1 : 0
  project               = var.k8s_project_id
  display_name          = "${local.name_prefix}: backend container restarted"
  combiner              = "OR"
  notification_channels = local.alert_k8s_channels

  conditions {
    display_name = "Backend container restart count went up"
    condition_threshold {
      filter          = "${local.alert_backend_container_filter} AND metric.type=\"kubernetes.io/container/restart_count\""
      comparison      = "COMPARISON_GT"
      threshold_value = 0
      duration        = "0s"
      aggregations {
        alignment_period     = "600s"
        per_series_aligner   = "ALIGN_DELTA"
        cross_series_reducer = "REDUCE_SUM"
        group_by_fields      = ["resource.labels.pod_name"]
      }
    }
  }

  documentation {
    mime_type = "text/markdown"
    content   = "The backend container restarted: a crash, a failed liveness probe, or the kernel killing it for memory. `kubectl -n ${local.name_prefix} describe pod <pod>` shows the last state and its reason."
  }
}

# Autopilot sets each container's memory limit to its request, so the
# backend can be killed for memory well before a node runs short.
resource "google_monitoring_alert_policy" "backend_memory" {
  count                 = local.alerting_enabled ? 1 : 0
  project               = var.k8s_project_id
  display_name          = "${local.name_prefix}: backend memory near its limit"
  combiner              = "OR"
  notification_channels = local.alert_k8s_channels

  conditions {
    display_name = "Memory above 90% of the limit for 10 minutes"
    condition_threshold {
      filter          = "${local.alert_backend_container_filter} AND metric.type=\"kubernetes.io/container/memory/limit_utilization\" AND metric.labels.memory_type=\"non-evictable\""
      comparison      = "COMPARISON_GT"
      threshold_value = 0.9
      duration        = "600s"
      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_MAX"
      }
    }
  }

  documentation {
    mime_type = "text/markdown"
    content   = "The backend is close to its memory limit and will be killed if it grows further. Raise resources.requests.memory in the Helm values, or find what is holding memory."
  }
}

resource "google_monitoring_alert_policy" "backend_evicted" {
  count                 = local.alerting_enabled ? 1 : 0
  project               = var.k8s_project_id
  display_name          = "${local.name_prefix}: pod evicted or killed for memory"
  combiner              = "OR"
  notification_channels = local.alert_k8s_channels

  conditions {
    display_name = "Kubernetes event: Evicted or OOMKilling"
    condition_matched_log {
      filter = "logName=\"projects/${var.k8s_project_id}/logs/events\" AND jsonPayload.involvedObject.namespace=\"${local.name_prefix}\" AND jsonPayload.reason=(\"Evicted\" OR \"OOMKilling\")"
    }
  }

  alert_strategy {
    notification_rate_limit {
      period = "3600s"
    }
    auto_close = "86400s"
  }

  documentation {
    mime_type = "text/markdown"
    content   = "Kubernetes evicted a pod in ${local.name_prefix} or killed one of its processes for memory. Look at the event, then at the node's memory."
  }
}

resource "google_logging_metric" "backend_errors" {
  count   = local.alerting_enabled ? 1 : 0
  project = var.k8s_project_id
  name    = "${local.name_prefix}-backend-errors"
  # stdout only: the app logs there, while stderr carries native library noise
  # such as gRPC's shutdown timeout on every pod stop.
  filter = "${local.alert_backend_container_filter} AND logName=\"projects/${var.k8s_project_id}/logs/stdout\" AND severity>=ERROR"

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
    unit        = "1"
  }
}

# uvicorn's access line ends in the status code: `... "GET /x HTTP/1.1" 500`.
resource "google_logging_metric" "backend_5xx" {
  count   = local.alerting_enabled ? 1 : 0
  project = var.k8s_project_id
  name    = "${local.name_prefix}-backend-5xx"
  filter  = "${local.alert_backend_container_filter} AND jsonPayload.name=\"uvicorn.access\" AND jsonPayload.message=~\"HTTP/[0-9.]+\\\" 5[0-9][0-9]$\""

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
    unit        = "1"
  }
}

resource "google_monitoring_alert_policy" "backend_errors" {
  count                 = local.alerting_enabled ? 1 : 0
  project               = var.k8s_project_id
  display_name          = "${local.name_prefix}: backend logging errors"
  combiner              = "OR"
  notification_channels = local.alert_k8s_channels

  conditions {
    display_name = "5 or more ERROR log lines in 5 minutes"
    condition_threshold {
      filter          = "resource.type=\"k8s_container\" AND metric.type=\"logging.googleapis.com/user/${google_logging_metric.backend_errors[0].name}\""
      comparison      = "COMPARISON_GT"
      threshold_value = 4
      duration        = "0s"
      aggregations {
        alignment_period     = "300s"
        per_series_aligner   = "ALIGN_DELTA"
        cross_series_reducer = "REDUCE_SUM"
      }
    }
  }

  documentation {
    mime_type = "text/markdown"
    content   = "The backend logged several errors in a short time. Open Logs Explorer in this project, filter on namespace ${local.name_prefix} and severity ERROR."
  }
}

resource "google_monitoring_alert_policy" "backend_5xx" {
  count                 = local.alerting_enabled ? 1 : 0
  project               = var.k8s_project_id
  display_name          = "${local.name_prefix}: backend answering 5xx"
  combiner              = "OR"
  notification_channels = local.alert_k8s_channels

  conditions {
    display_name = "5 or more 5xx responses in 5 minutes"
    condition_threshold {
      filter          = "resource.type=\"k8s_container\" AND metric.type=\"logging.googleapis.com/user/${google_logging_metric.backend_5xx[0].name}\""
      comparison      = "COMPARISON_GT"
      threshold_value = 4
      duration        = "0s"
      aggregations {
        alignment_period     = "300s"
        per_series_aligner   = "ALIGN_DELTA"
        cross_series_reducer = "REDUCE_SUM"
      }
    }
  }

  documentation {
    mime_type = "text/markdown"
    content   = "The backend answered several requests with a 5xx. The access lines are in Logs Explorer under namespace ${local.name_prefix}; the matching ERROR lines usually sit just before them."
  }
}

# ---------------------------------------------------------------------------
# CronJobs (cluster project)
# ---------------------------------------------------------------------------

# Kubernetes retries a failed run until the Job's backoff limit, then records
# BackoffLimitExceeded; a run past activeDeadlineSeconds records
# DeadlineExceeded. Alerting on these, not on each cron.failed line, reports
# only runs that still failed after every retry.
resource "google_monitoring_alert_policy" "cron_job_failed" {
  count                 = local.alerting_enabled ? 1 : 0
  project               = var.k8s_project_id
  display_name          = "${local.name_prefix}: cron job failed after retries"
  combiner              = "OR"
  notification_channels = local.alert_k8s_channels

  conditions {
    display_name = "Kubernetes event: BackoffLimitExceeded or DeadlineExceeded on a Job"
    condition_matched_log {
      filter = "logName=\"projects/${var.k8s_project_id}/logs/events\" AND jsonPayload.involvedObject.namespace=\"${local.name_prefix}\" AND jsonPayload.involvedObject.kind=\"Job\" AND jsonPayload.reason=(\"BackoffLimitExceeded\" OR \"DeadlineExceeded\")"
      label_extractors = {
        job = "EXTRACT(jsonPayload.involvedObject.name)"
      }
    }
  }

  alert_strategy {
    notification_rate_limit {
      period = "3600s"
    }
    auto_close = "86400s"
  }

  documentation {
    mime_type = "text/markdown"
    content   = "A cron job still failed after Kubernetes retried it. The job name is in the alert labels. Its `cron.failed` lines in Logs Explorer (namespace ${local.name_prefix}, jsonPayload.monitor_event=\"cron.failed\") give curl's exit code: 22 means the backend answered 4xx or 5xx, 7 that it could not connect, 28 a timeout. The backend's own logs at that time give the cause."
  }
}

resource "google_logging_metric" "cron_succeeded" {
  count   = local.alerting_enabled ? 1 : 0
  project = var.k8s_project_id
  name    = "${local.name_prefix}-cron-succeeded"
  filter  = "resource.type=\"k8s_container\" AND resource.labels.namespace_name=\"${local.name_prefix}\" AND jsonPayload.monitor_event=\"cron.succeeded\""

  label_extractors = {
    job = "EXTRACT(jsonPayload.job)"
  }

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
    unit        = "1"
    labels {
      key        = "job"
      value_type = "STRING"
    }
  }
}

# sync-meet-attendance runs every two hours, so six hours without a success
# means the cron jobs as a whole have stopped running, which no failure event
# would report. The other jobs run daily or less often, beyond the one-day
# limit of an absence condition.
resource "google_monitoring_alert_policy" "cron_stopped" {
  count                 = local.alerting_enabled ? 1 : 0
  project               = var.k8s_project_id
  display_name          = "${local.name_prefix}: cron jobs stopped running"
  combiner              = "OR"
  notification_channels = local.alert_k8s_channels

  conditions {
    display_name = "No successful sync-meet-attendance run for 6 hours"
    condition_absent {
      filter   = "resource.type=\"k8s_container\" AND metric.type=\"logging.googleapis.com/user/${google_logging_metric.cron_succeeded[0].name}\" AND metric.labels.job=\"sync-meet-attendance\""
      duration = "21600s"
      aggregations {
        alignment_period     = "300s"
        per_series_aligner   = "ALIGN_DELTA"
        cross_series_reducer = "REDUCE_SUM"
      }
    }
  }

  documentation {
    mime_type = "text/markdown"
    content   = "sync-meet-attendance, which runs every two hours, has not succeeded for six hours. Either it keeps failing (look for the failed-after-retries alert), or no cron job is being scheduled: check `kubectl -n ${local.name_prefix} get cronjobs` for suspended jobs and the cluster for trouble."
  }
}
