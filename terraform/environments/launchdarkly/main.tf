locals {
  ld_envs = {
    test = {
      display_name = "Test"
      color        = "f9a825"
      beta_gated   = false
    }
    staging = {
      display_name = "Staging"
      color        = "1e88e5"
      beta_gated   = true
    }
    production = {
      display_name = "Production"
      color        = "0b7a3e"
      beta_gated   = true
    }
  }

  flags = {
    manual_submit_meeting = {
      key         = "manual-submit-meeting"
      name        = "Manual Submit Meeting"
      description = "Enables the manual meeting submit flow"
      off_in      = []
      public_in   = []
    }
    view_personal_summary = {
      key         = "view-personal-summary"
      name        = "View Personal Summary"
      description = "Enables the view personal summary feature"
      off_in      = []
      public_in   = ["staging", "production"]
    }
    create_google_meeting = {
      key         = "create-google-meeting"
      name        = "Create Google Meeting"
      description = "Enables the Google Meeting related feature"
      off_in      = ["staging", "production"]
      public_in   = []
    }
  }

  flag_env_matrix = {
    for pair in setproduct(keys(local.flags), keys(local.ld_envs)) :
    "${pair[0]}/${pair[1]}" => {
      flag_id    = pair[0]
      env_key    = pair[1]
      beta_gated = local.ld_envs[pair[1]].beta_gated && !contains(local.flags[pair[0]].public_in, pair[1])
      on         = !contains(local.flags[pair[0]].off_in, pair[1])
    }
  }
}

resource "launchdarkly_project" "purrf" {
  key  = "purrf"
  name = "Purrf"

  environments {
    key   = "test"
    name  = local.ld_envs.test.display_name
    color = local.ld_envs.test.color
  }

  environments {
    key   = "staging"
    name  = local.ld_envs.staging.display_name
    color = local.ld_envs.staging.color
  }

  environments {
    key              = "production"
    name             = local.ld_envs.production.display_name
    color            = local.ld_envs.production.color
    confirm_changes  = true
    require_comments = true
  }

  default_client_side_availability {
    using_environment_id = true
    using_mobile_key     = true
  }

  tags = ["managed-by-terraform"]
}

resource "launchdarkly_segment" "beta_users" {
  for_each = local.ld_envs

  key         = "beta-users"
  project_key = launchdarkly_project.purrf.key
  env_key     = each.key
  name        = "Beta Users"
  description = "Users with ccInternal role for beta feature access"

  rules {
    clauses {
      attribute = "roles"
      op        = "contains"
      values    = ["ccInternal"]
    }
  }
}

resource "launchdarkly_feature_flag" "this" {
  for_each = local.flags

  project_key    = launchdarkly_project.purrf.key
  key            = each.value.key
  name           = each.value.name
  description    = each.value.description
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

resource "launchdarkly_feature_flag_environment" "this" {
  for_each = local.flag_env_matrix

  flag_id = launchdarkly_feature_flag.this[each.value.flag_id].id
  env_key = each.value.env_key

  on = each.value.on

  dynamic "rules" {
    for_each = each.value.beta_gated ? [1] : []
    content {
      clauses {
        attribute = "context"
        op        = "segmentMatch"
        values    = [launchdarkly_segment.beta_users[each.value.env_key].key]
      }
      variation = 0
    }
  }

  fallthrough {
    variation = each.value.beta_gated ? 1 : 0
  }

  off_variation = 1
}
