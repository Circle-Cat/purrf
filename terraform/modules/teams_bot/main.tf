data "azuread_client_config" "current" {}

# The bot's identity. Single tenant: it can only message people in our own
# Microsoft 365 tenant.
resource "azuread_application" "bot" {
  display_name     = coalesce(var.display_name, var.name)
  sign_in_audience = "AzureADMyOrg"
  owners           = [data.azuread_client_config.current.object_id]
}

resource "azuread_service_principal" "bot" {
  client_id = azuread_application.bot.client_id
  owners    = [data.azuread_client_config.current.object_id]
}

resource "azuread_application_federated_identity_credential" "bot" {
  for_each = var.federated_identities

  application_id = azuread_application.bot.id
  display_name   = "${var.name}-${each.key}"
  audiences      = ["api://AzureADTokenExchange"]
  issuer         = each.value.issuer
  subject        = each.value.subject
}

resource "azurerm_resource_group" "bot" {
  name     = var.name
  location = var.location
}

# Notification-only bot: it never receives messages, so it has no messaging
# endpoint.
resource "azurerm_bot_service_azure_bot" "bot" {
  name                    = var.name
  display_name            = coalesce(var.display_name, var.name)
  resource_group_name     = azurerm_resource_group.bot.name
  location                = "global"
  sku                     = "F0"
  microsoft_app_id        = azuread_application.bot.client_id
  microsoft_app_type      = "SingleTenant"
  microsoft_app_tenant_id = data.azuread_client_config.current.tenant_id
}

resource "azurerm_bot_channel_ms_teams" "bot" {
  bot_name            = azurerm_bot_service_azure_bot.bot.name
  resource_group_name = azurerm_resource_group.bot.name
  location            = azurerm_bot_service_azure_bot.bot.location
}
