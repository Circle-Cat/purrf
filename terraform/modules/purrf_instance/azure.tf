resource "azuread_application_federated_identity_credential" "azure_wif" {
  application_id = "/applications/39092dd4-3b42-4b40-9d46-ed7ca4854e17"
  audiences      = ["api://AzureADTokenExchange"]
  description    = null
  display_name   = local.name_prefix
  issuer         = "https://container.googleapis.com/v1/projects/circlecat/locations/us-west1/clusters/dev"
  subject        = "system:serviceaccount:${local.name_prefix}:${local.name_prefix}"
}