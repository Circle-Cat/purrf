resource "azuread_application_federated_identity_credential" "azure_wif" {
  application_id = "/applications/39092dd4-3b42-4b40-9d46-ed7ca4854e17"
  audiences      = ["api://AzureADTokenExchange"]
  description    = null
  display_name   = local.name_prefix
  issuer         = "https://container.googleapis.com/v1/projects/${var.k8s_project_id}/locations/${var.k8s_cluster_location}/clusters/${var.k8s_cluster_name}"
  subject        = "system:serviceaccount:${local.name_prefix}:${local.name_prefix}"
}

resource "azuread_application_federated_identity_credential" "azure_wif_cf" {
  application_id = "/applications/39092dd4-3b42-4b40-9d46-ed7ca4854e17"
  display_name   = "${local.name_prefix}-cf"
  audiences      = ["api://AzureADTokenExchange"]
  issuer         = "https://accounts.google.com"
  subject        = google_service_account.function_sa.unique_id
}
