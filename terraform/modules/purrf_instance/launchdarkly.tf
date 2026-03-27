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

  fallthrough {
    variation = 0
  }
  off_variation = 1

}

locals {
  ld_environment    = launchdarkly_project.purrf.environments[0]
  ld_sdk_key        = local.ld_environment.api_key
  ld_client_side_id = local.ld_environment.client_side_id
}
