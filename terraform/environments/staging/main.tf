data "terraform_remote_state" "ld" {
  backend = "gcs"
  config = {
    bucket = "purrf-terraform-state"
    prefix = "launchdarkly"
  }
}

# Create a Purrf instance for the staging environment.
module "purrf_instance" {
  source = "../../modules/purrf_instance"

  env_name                   = "staging"
  gcp_project_id             = "purrf-452300"
  k8s_project_id             = "circlecat-prod-iad"
  k8s_cluster_name           = "prod"
  k8s_cluster_location       = "us-east4"
  gcp_region                 = "us-east4"
  ingress_class_name         = "cloudflare2-tunnel"
  auth0_callbacks            = ["https://ccat-dev.cloudflareaccess.com/cdn-cgi/access/callback"]
  auth0_logout_urls          = ["https://ccat-dev.cloudflareaccess.com/cdn-cgi/access/logout"]
  neon_org_id                = "org-restless-scene-93869523"
  cloudflare_account_id      = "0fc5fc1f83592f6c1bdc89b240469324"
  cloudflare_zone_id         = "9a0308ba411ef3466582881dcd274f18"
  microsoft_chat_code_dir    = "../../../backend/producers/microsoft_chat_producer"
  microsoft_chat_entry_point = "notification_webhook"

  microsoft_lifecycle_code_dir    = "../../../backend/producers/microsoft_lifecycle_notification_handler"
  microsoft_lifecycle_entry_point = "lifecycle_notification_webhook"

  gerrit_producer_code_dir    = "../../../backend/producers/gerrit_producer"
  gerrit_producer_entry_point = "gerrit_event_webhook"
  jira_password               = var.jira_password
  gerrit_http_pass            = var.gerrit_http_pass
  image_tag                   = "20260428-140603"
  cf_aud_tag                  = "3a069a38522a7ef33aed95d4e58671081380c261391fa14d3433f637f4a0da2a"
  azure_client_id             = "8f3f85f2-be71-4ed5-95e8-3c777f4c6e13"
  azure_tenant_id             = "08502fd6-503a-4dfd-85b7-f13b141dc0c4"
  ld_sdk_key                  = data.terraform_remote_state.ld.outputs.api_keys["staging"]
  tailscale_proxy             = "http://outbound.tailscale.svc.cluster.local:1055"
}
