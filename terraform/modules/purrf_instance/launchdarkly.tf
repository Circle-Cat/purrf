resource "launchdarkly_project" "purrf" {
  key  = local.name_prefix
  name = "Purrf ${var.env_name}"

  environments {
    key   = "production"
    name  = "Production"
    color = "0b7a3e"
  }

  tags = ["managed-by-terraform"]
}

resource "launchdarkly_feature_flag" "manual_submit_meeting" {
  project_key    = launchdarkly_project.purrf.key
  key            = "manual-submit-meeting"
  name           = "Manual Submit Meeting"
  description    = "Enables the manual meeting submit flow"
  variation_type = "boolean"

  variations {
    value = "true"
  }

  variations {
    value = "false"
  }

  defaults {
    on_variation  = 0
    off_variation = 1
  }

  tags = ["managed-by-terraform"]
}

resource "launchdarkly_feature_flag_environment" "manual_submit_meeting" {
  flag_id = launchdarkly_feature_flag.manual_submit_meeting.id
  env_key = "production"

  on = true

  dynamic "rules" {
    for_each = var.beta_enabled ? [1] : []
    content {
      clauses {
        attribute = "context"
        op        = "segmentMatch"
        values    = [var.beta_segment_key]
      }
      variation = 0
    }
  }

  fallthrough {
    variation = var.beta_enabled ? 1 : 0
  }

  off_variation = 1
}

resource "launchdarkly_feature_flag" "view_personal_summary" {
  project_key    = launchdarkly_project.purrf.key
  key            = "view-personal-summary"
  name           = "View Personal Summary"
  description    = "Enables the view personal summary feature"
  variation_type = "boolean"

  variations {
    value = "true"
  }

  variations {
    value = "false"
  }

  defaults {
    on_variation  = 0
    off_variation = 1
  }

  tags = ["managed-by-terraform"]
}
