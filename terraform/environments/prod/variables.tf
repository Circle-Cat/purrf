variable "jira_password" {
  type      = string
  sensitive = true
}

variable "gerrit_http_pass" {
  type      = string
  sensitive = true
}

variable "gmail_client_id" {
  description = "OAuth 2.0 client ID for the Gmail candidate-email integration (purrf-452300 GCP project; users.watch requires the topic and the client in the same project)."
  type        = string
}

variable "gmail_client_secret" {
  description = "OAuth 2.0 client secret paired with gmail_client_id (purrf-452300 GCP project)."
  type        = string
  sensitive   = true
}

variable "gmail_refresh_token" {
  description = "OAuth refresh token for the sender mailbox. Minted once via interactive consent; supply via TF_VAR."
  type        = string
  sensitive   = true
}
