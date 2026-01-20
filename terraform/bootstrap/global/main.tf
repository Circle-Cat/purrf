resource "cloudflare_ruleset" "cors_headers" {
  zone_id = "9a0308ba411ef3466582881dcd274f18"
  name    = "default"
  kind    = "zone"
  phase   = "http_response_headers_transform"

  rules = [
    for env in local.environments : {
      action      = "rewrite"
      description = "CORS Header for Purrf ${env.name}"
      enabled     = true

      expression = "(http.host eq \"${env.api_host}\" and http.request.uri.path wildcard r\"/api/*\")"

      action_parameters = {
        headers = {
          "Access-Control-Allow-Origin" = {
            operation = "set"
            value     = "https://${env.origin_web}"
          }
          "Access-Control-Allow-Methods" = {
            operation = "set"
            value     = "GET, POST, OPTIONS, DELETE, PUT"
          }
          "Access-Control-Allow-Headers" = {
            operation = "set"
            value     = "Content-Type, Authorization"
          }
          "Access-Control-Allow-Credentials" = {
            operation = "set"
            value     = "true"
          }
        }
      }
    }
  ]
}
