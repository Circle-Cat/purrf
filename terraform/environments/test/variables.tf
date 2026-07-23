variable "jira_password" {
  type      = string
  sensitive = true
}

variable "gerrit_http_pass" {
  type      = string
  sensitive = true
}

variable "auth0_google_client_id" {
  description = "OAuth 2.0 Web Client ID from the purrf-auth GCP project, backing the Auth0 Google social connection."
  type        = string
}

variable "auth0_google_client_secret" {
  description = "OAuth 2.0 client secret paired with auth0_google_client_id (purrf-auth GCP project)."
  type        = string
  sensitive   = true
}

variable "gmail_client_id" {
  description = "OAuth 2.0 client ID for the Gmail candidate-email integration (purrf-auth GCP project)."
  type        = string
}

variable "gmail_client_secret" {
  description = "OAuth 2.0 client secret paired with gmail_client_id (purrf-auth GCP project)."
  type        = string
  sensitive   = true
}

variable "gmail_refresh_token" {
  description = "OAuth refresh token for the sender mailbox. Minted once via interactive consent; supply via TF_VAR."
  type        = string
  sensitive   = true
}

variable "gmail_sender_address" {
  description = "Mailbox the app sends candidate emails from (a test mailbox in this environment)."
  type        = string
}


