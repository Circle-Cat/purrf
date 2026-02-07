# Create a Purrf instance for the test environment.
module "purrf_instance" {
  source = "../../modules/purrf_instance"

  env_name              = "test"
  gcp_project_id        = "purrf-452300"
  auth0_callbacks       = ["https://ccat-dev.cloudflareaccess.com/cdn-cgi/access/callback"]
  auth0_logout_urls     = ["https://ccat-dev.cloudflareaccess.com/cdn-cgi/access/logout"]
  neon_org_id           = "org-restless-scene-93869523"
  cloudflare_account_id = "0fc5fc1f83592f6c1bdc89b240469324"
  cloudflare_zone_id    = "9a0308ba411ef3466582881dcd274f18"
  cloudflare_tunnel_id  = "dd604706-9340-414a-8afb-2bf673049bbd"

  microsoft_chat_code_dir    = "../../../backend/producers/microsoft_chat_producer"
  microsoft_chat_entry_point = "notification_webhook"

  microsoft_lifecycle_code_dir    = "../../../backend/producers/microsoft_lifecycle_notification_handler"
  microsoft_lifecycle_entry_point = "lifecycle_notification_webhook"

  gerrit_producer_code_dir    = "../../../backend/producers/gerrit_producer"
  gerrit_producer_entry_point = "gerrit_event_webhook"
  jira_password               = var.jira_password
  gerrit_http_pass            = var.gerrit_http_pass
  image_tag                   = "20260203-163352"
  cf_aud_tag                  = "8187a0acb20eed9fe7b5d2290977c85490f6c7f3844595f521dc6f3328ca37d0"
  azure_client_id             = "8f3f85f2-be71-4ed5-95e8-3c777f4c6e13"
  azure_tenant_id             = "08502fd6-503a-4dfd-85b7-f13b141dc0c4"
  azure_client_secert         = var.azure_client_secert
}

