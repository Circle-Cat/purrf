# Credentials the notification gateway Worker authenticates to the backend
# with. Terraform creates and owns the service tokens; it does not set them on
# the Worker, because provider v5 has no Worker-secret resource and the only
# resource that could carry one (cloudflare_workers_script) owns the script
# body too, which would fight the Worker's own deploy for ownership.
#
# So the two halves are joined by hand, once per token, in the Worker's
# Settings > Variables & Secrets (or `wrangler secret put`):
#
#   terraform -chdir=terraform/bootstrap/global output -json \
#     notification_gateway_service_tokens
#
#   CF_ACCESS_CLIENT_ID      <- .<env>.client_id
#   CF_ACCESS_CLIENT_SECRET  <- .<env>.client_secret
#
# The Worker's third secret, ALLOWED_SUBS, comes from the other state -- the
# push service account lives in the per-environment configuration:
#
#   terraform -chdir=terraform/environments/<env> output notification_pusher_sub
#
# The token does not expire. Rotating one is a deliberate act: taint it,
# re-run this configuration, read the new output, and update the Worker's
# secrets. Nothing does any of that on its own, and the Worker keeps
# presenting the old credential until someone does.
output "notification_gateway_service_tokens" {
  description = "Access service token credentials for the notification gateway Worker, keyed by environment. Set on the Worker out of band; see the comment above."
  sensitive   = true
  value = {
    test = {
      client_id     = cloudflare_zero_trust_access_service_token.notification_gateway_test.client_id
      client_secret = cloudflare_zero_trust_access_service_token.notification_gateway_test.client_secret
    }
    staging = {
      client_id     = cloudflare_zero_trust_access_service_token.notification_gateway_staging.client_id
      client_secret = cloudflare_zero_trust_access_service_token.notification_gateway_staging.client_secret
    }
  }
}
