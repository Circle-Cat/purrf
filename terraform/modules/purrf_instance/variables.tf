variable "env_name" {
  description = "Environment name: prod, test, or staging"
  type        = string
  validation {
    condition     = contains(["prod", "test", "staging"], var.env_name)
    error_message = "env_name must be one of: prod, test, staging."
  }
}

variable "base_domain" {
  description = "Base domain name"
  type        = string
  default     = "purrf.io"
}

variable "gcp_project_id" {
  description = "GCP project ID"
  type        = string
}

variable "gcp_region" {
  description = "GCP region"
  type        = string
  default     = "us-west1"
}

variable "neon_org_id" {
  type = string
}

variable "cloudflare_account_id" {
  description = "Cloudflare Account ID"
  type        = string
}

variable "cloudflare_zone_id" {
  description = "Cloudflare Zone ID"
  type        = string
}

variable "cloudflare_tunnel_id" {
  description = "Cloudflare Tunnel ID"
  type        = string
}

variable "microsoft_chat_code_dir" {
  type        = string
  description = "The relative path to the Microsoft Chat producer source code directory."
}

variable "microsoft_chat_entry_point" {
  type        = string
  description = "The name of the Python function to be executed for Microsoft Chat."
}

variable "microsoft_lifecycle_code_dir" {
  type        = string
  description = "The relative path to the Microsoft Lifecycle handler source code directory."
}

variable "microsoft_lifecycle_entry_point" {
  type        = string
  description = "The name of the Python function to be executed for Microsoft Lifecycle events."
}

variable "gerrit_producer_code_dir" {
  type        = string
  description = "The relative path to the Gerrit producer source code directory."
}

variable "gerrit_producer_entry_point" {
  type        = string
  description = "The name of the Python function to be executed for Gerrit events."
}

variable "auth0_callbacks" {
  type        = list(string)
  description = "Allowed callback URLs for Auth0"
}

variable "auth0_logout_urls" {
  type        = list(string)
  description = "Allowed logout URLs for Auth0"
}

variable "image_tag" {
  type        = string
  description = "Deployed image tag"
}

variable "jira_password" {
  type      = string
  sensitive = true
}

variable "gerrit_http_pass" {
  type      = string
  sensitive = true
}

variable "cf_aud_tag" {
  type = string
}

variable "azure_client_id" {
  type = string
}

variable "azure_client_secert" {
  type      = string
  sensitive = true
}

variable "azure_tenant_id" {
  type = string
}

variable "beta_enabled" {
  description = "When true, feature flags target beta segment only. When false, flags are fully released to all users."
  type        = bool
  default     = false
}

variable "beta_segment_key" {
  description = "LaunchDarkly segment key for beta users"
  type        = string
  default     = ""
}
