output "app_id" {
  description = "Application (client) ID of the bot; the botId in the Teams app manifest."
  value       = azuread_application.bot.client_id
}

output "tenant_id" {
  description = "Tenant the bot belongs to."
  value       = data.azuread_client_config.current.tenant_id
}
