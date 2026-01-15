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

locals {
  # Derived values based on environment configuration
  is_prod = var.env_name == "prod"

  name_prefix = "purrf-${var.env_name}"

  subdomain_prefix  = local.is_prod ? "" : "${var.env_name}-"
  env_domain_prefix = local.is_prod ? "" : "${var.env_name}."

  domains = {
    main  = "${local.env_domain_prefix}${var.base_domain}"
    api   = "${local.subdomain_prefix}api.${var.base_domain}"
    login = "${local.subdomain_prefix}login.${var.base_domain}"
    cf    = "${local.subdomain_prefix}cf.${var.base_domain}"
  }

  common_labels = {
    env        = var.env_name
    managed_by = "terraform"
    project    = "purrf"
  }
}

